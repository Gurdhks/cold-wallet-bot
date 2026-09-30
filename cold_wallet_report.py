"""
Fetches live cold wallet balances, compares each against its most recent
successful prior snapshot in balance_history.json, and posts a report
(with day-over-day absolute and percentage diffs, labeled with the SGT
capture time) to Slack. Saves today's snapshot for the next comparison.

A balance that can't be fetched shows as ERROR, the reason is listed under
the table, and it is saved as null so it is never used as a comparison point.
"""
import csv
import json
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests
from address_validators import validate_address
from balance_fetchers import BALANCE_FETCHERS

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
SLACK_WEBHOOK_URL_2 = os.environ.get("SLACK_WEBHOOK_URL_2", "")
HISTORY_FILE = "balance_history.json"
SGT = ZoneInfo("Asia/Singapore")
BAL_WIDTH = 17  # wide enough for VET-sized balances


def post_to_slack(text: str):
    for url in [SLACK_WEBHOOK_URL, SLACK_WEBHOOK_URL_2]:
        if not url:
            continue
        try:
            r = requests.post(url, json={"text": text}, timeout=20)
            r.raise_for_status()
        except Exception as e:
            print(f"Failed to post to Slack webhook: {e}")


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {}
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, sort_keys=True)


def most_recent_prior_date(history, today_str):
    past_dates = [d for d in history.keys() if d < today_str]
    if not past_dates:
        return None
    return max(past_dates)


def last_good_value(history, today_str, symbol):
    """Most recent prior date where this symbol has a real (non-null) balance."""
    for d in sorted((d for d in history if d < today_str), reverse=True):
        value = history[d].get("balances", {}).get(symbol)
        if value is not None:
            return d, value
    return None, None


def format_sgt(iso_str: str) -> str:
    dt = datetime.fromisoformat(iso_str).astimezone(SGT)
    return dt.strftime("%Y-%m-%d %I:%M %p SGT")


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "addresses.csv"
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k: (v or "").strip() for k, v in row.items()})

    results = {}
    errors = {}
    for row in rows:
        symbol = row["symbol"]
        network_id = row["network_id"]
        address = row["address"]

        try:
            valid = validate_address(network_id, address)
        except ValueError:
            valid = None  # no validator for this network; still try to fetch
        if valid is False:
            results[symbol] = None
            errors[symbol] = f"invalid {network_id} address format"
            continue

        fetcher = BALANCE_FETCHERS.get(network_id)
        if fetcher is None:
            results[symbol] = None
            errors[symbol] = f"no fetcher for network_id '{network_id}'"
            continue

        try:
            results[symbol] = fetcher(address)
        except Exception as e:
            results[symbol] = None
            errors[symbol] = str(e)[:300]

    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")

    history = load_history()
    prior_date = most_recent_prior_date(history, today_str)
    prior_captured_at = history.get(prior_date, {}).get("captured_at") if prior_date else None

    lines = []
    for row in rows:
        sym = row["symbol"]
        current = results[sym]
        if current is None:
            lines.append(f"{sym:<8} {'ERROR':>{BAL_WIDTH}}")
            continue

        line = f"{sym:<8} {current:>{BAL_WIDTH},.4f}"
        cmp_date, prior = last_good_value(history, today_str, sym)
        if prior is not None:
            diff = current - prior
            if abs(diff) < 1e-9:
                diff = 0.0
            sign = "+" if diff >= 0 else ""
            if prior != 0:
                pct_str = f"{sign}{(diff / prior) * 100:,.2f}%"
            else:
                pct_str = "N/A"
            line += f"  ({sign}{diff:,.4f}, {pct_str})"
            if cmp_date != prior_date:
                line += f"  [vs {cmp_date}]"
        lines.append(line)

    if prior_date and prior_captured_at:
        header = f"*Cold wallet balances* (vs {format_sgt(prior_captured_at)})"
    else:
        header = "*Cold wallet balances* (no prior snapshot yet)"

    msg = f"{header}\n```" + "\n".join(lines) + "```"
    if errors:
        err_lines = "\n".join(f"• {sym}: {err}" for sym, err in errors.items())
        msg += f"\n\n:warning: *Fetch errors:*\n{err_lines}"

    print(msg)
    post_to_slack(msg)

    history[today_str] = {
        "captured_at": now_utc.isoformat(),
        "balances": results,
    }
    save_history(history)


if __name__ == "__main__":
    main()
