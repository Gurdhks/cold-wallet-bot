"""
Debug script — prints the raw API response for each live cold wallet chain,
so problems can be fixed based on real data instead of guesses.

Reads addresses from addresses.csv, so it always checks the same wallets
the report uses. Uses the same endpoints as balance_fetchers.py.

Usage:
    python debug_balances.py                  # all chains
    python debug_balances.py icp vechain      # only these network_ids

To test a new chain before writing its fetcher, add a function to RAW_CALLS
below with the same network_id you will use in addresses.csv.
"""

import csv
import json
import sys
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (ColdWalletBot/1.0)"}


def raw_aptos(address):
    payload = {
        "function": "0x1::coin::balance",
        "type_arguments": ["0x1::aptos_coin::AptosCoin"],
        "arguments": [address],
    }
    return requests.post("https://fullnode.mainnet.aptoslabs.com/v1/view",
                         json=payload, headers=HEADERS, timeout=25)


def raw_arweave(address):
    return requests.get(f"https://arweave.net/wallet/{address}/balance",
                        headers=HEADERS, timeout=25)


def raw_icp(address):
    return requests.get(f"https://ledger-api.internetcomputer.org/accounts/{address}",
                        headers=HEADERS, timeout=25)


def raw_vechain(address):
    return requests.get(f"https://mainnet.vecha.in/accounts/{address}",
                        headers=HEADERS, timeout=25)


RAW_CALLS = {
    "aptos":   raw_aptos,
    "arweave": raw_arweave,
    "icp":     raw_icp,
    "vechain": raw_vechain,
}


def show(label, resp):
    print(f"\n===== {label} (HTTP {resp.status_code}) =====")
    try:
        print(json.dumps(resp.json(), indent=2)[:1500])
    except ValueError:
        print(resp.text[:1500])


def main():
    only = {a.lower() for a in sys.argv[1:]}
    with open("addresses.csv", newline="", encoding="utf-8") as f:
        rows = [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]

    for row in rows:
        net, sym, addr = row["network_id"], row["symbol"], row["address"]
        if only and net not in only:
            continue
        call = RAW_CALLS.get(net)
        if call is None:
            print(f"\n===== {sym} ({net}) =====\nNo raw call defined for this network_id.")
            continue
        try:
            show(f"{sym} ({net})", call(addr))
        except Exception as e:
            print(f"\n===== {sym} ({net}) ERROR =====\n{e}")


if __name__ == "__main__":
    main()
