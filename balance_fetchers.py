"""
Balance fetcher for cold-wallet-bot addresses.
Covers: APT, AR, ICP, VET
"""

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (ColdWalletBot/1.0)"}


def safe_get_json(url, timeout=25, headers=None):
    r = requests.get(url, headers=headers or HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()


def safe_post_json(url, payload, timeout=25, headers=None):
    r = requests.post(url, json=payload, headers=headers or HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ── APT (Aptos) ──────────────────────────────────────────────────────────────

def get_apt_balance(address: str) -> float:
    url = "https://fullnode.mainnet.aptoslabs.com/v1/view"
    payload = {
        "function": "0x1::coin::balance",
        "type_arguments": ["0x1::aptos_coin::AptosCoin"],
        "arguments": [address],
    }
    out = safe_post_json(url, payload)
    octas = int(out[0])
    return octas / 1e8


# ── AR (Arweave) ─────────────────────────────────────────────────────────────

def get_ar_balance(address: str) -> float:
    url = f"https://arweave.net/wallet/{address}/balance"
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    winston = int(r.text.strip())
    return winston / 1e12


# ── ICP (Internet Computer) ──────────────────────────────────────────────────

def get_icp_balance(account_id: str) -> float:
    url = f"https://ledger-api.internetcomputer.org/accounts/{account_id}"
    data = safe_get_json(url)
    e8s = int(data["balance"])
    return e8s / 1e8


# ── VET (VeChain) ────────────────────────────────────────────────────────────

def get_vet_balance(address: str) -> float:
    url = f"https://mainnet.vecha.in/accounts/{address}"
    data = safe_get_json(url)
    wei = int(data["balance"], 16)
    return wei / 1e18


BALANCE_FETCHERS = {
    "aptos":   get_apt_balance,
    "arweave": get_ar_balance,
    "icp":     get_icp_balance,
    "vechain": get_vet_balance,
}
