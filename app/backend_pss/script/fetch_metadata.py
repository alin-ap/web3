#!/usr/bin/env python3
"""Fetch contract metadata from Etherscan and store it locally."""

import json
import sys
from pathlib import Path

import requests

API_KEY = "EMCUTSCTFIHUNFYK9AGEZFU9U9V7PNYNU7"
CHAIN_ID = "1"
OUTPUT_DIR = Path("metadata")


def main() -> None:
    if len(sys.argv) != 2:
        print("用法: python script/fetch_metadata.py <合约地址>")
        sys.exit(1)

    addr = sys.argv[1].lower()
    result = fetch_metadata(addr)
    write_metadata(addr, result)
    print(
        "ok:",
        {
            "address": addr,
            "contract": result.get("ContractName"),
            "compiler": result.get("CompilerVersion"),
            "optimizer": result.get("OptimizationUsed"),
            "runs": result.get("Runs"),
            "evm": result.get("EVMVersion"),
        },
    )


def fetch_metadata(address: str) -> dict:
    for url in (
        "https://api.etherscan.io/v2/api"
        f"?chainid={CHAIN_ID}&module=contract&action=getsourcecode&address={address}&apikey={API_KEY}",
        "https://api.etherscan.io/api"
        f"?module=contract&action=getsourcecode&address={address}&apikey={API_KEY}",
    ):
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        result = payload.get("result")
        if isinstance(result, list) and result:
            entry = result[0]
            if isinstance(entry, dict):
                return entry
    raise RuntimeError(f"Etherscan returned no metadata for {address}")


def write_metadata(address: str, entry: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    name = entry.get("ContractName", "unknown") or "unknown"
    path = OUTPUT_DIR / f"{name}_{address}.json"
    path.write_text(json.dumps(entry, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
