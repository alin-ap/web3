import json
import sys
from pathlib import Path

import requests


API_KEY = "EMCUTSCTFIHUNFYK9AGEZFU9U9V7PNYNU7"
CHAIN_ID = "1"

TARGET_DIR = Path("src/factory")
CONTRACT_ADDRESS = "0x05852ed6b0397F252969Ec6A92b26C725Bd975ff"


def fetch_sources(contract_address: str) -> None:
    addr = contract_address.lower()
    urls = [
        "https://api.etherscan.io/v2/api"
        f"?chainid={CHAIN_ID}&module=contract&action=getsourcecode&address={addr}&apikey={API_KEY}",
        "https://api.etherscan.io/api"
        f"?module=contract&action=getsourcecode&address={addr}&apikey={API_KEY}",
    ]

    for url in urls:
        payload = requests.get(url, timeout=30).json()
        result = payload.get("result")
        if isinstance(result, list) and result:
            entry = result[0]
            if isinstance(entry, dict):
                write_sources(entry)
                return

    raise RuntimeError(f"Etherscan returned no source for {addr}")


def write_sources(entry: dict) -> None:
    source_blob = entry.get("SourceCode", "")
    if source_blob.startswith("{{") and source_blob.endswith("}}"):  # pragma: no cover
        source_blob = source_blob[1:-1]

    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    data = json.loads(source_blob)
    for rel_path, obj in data["sources"].items():
        path = TARGET_DIR / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(obj["content"], encoding="utf-8")


def main() -> None:
    if CONTRACT_ADDRESS == "":
        print("请在脚本顶部设置 CONTRACT_ADDRESS")
        sys.exit(1)

    fetch_sources(CONTRACT_ADDRESS)
    print("ok")


if __name__ == "__main__":
    main()
