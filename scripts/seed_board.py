"""Put the whole board on chain.

The board is ``markets/seed_markets.json``. This script creates every market
in it on the network, one at a time, and keeps inside the network's budget:
creating a market costs seven requests and the network allows thirty a
minute, so the run is paced below that.

    python scripts/seed_board.py --network studionet --wallet tester1

The contract is deployed first, so the board lands on a contract of its own
unless ``--contract`` names one that already exists.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from genlayer_py import create_client, localnet, studionet, testnet_bradbury

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wallet import load_account  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "cite.py"
SEED_FILE = ROOT / "markets" / "seed_markets.json"

CHAINS = {
    "studionet": studionet,
    "localnet": localnet,
    "testnet_bradbury": testnet_bradbury,
}

# Seven requests and sixteen seconds per market, paced to stay under twenty
# requests a minute.
SECONDS_PER_MARKET = 22


def _to_ts(value: str) -> int:
    """ISO 8601 -> unix seconds. An empty string means "not set"."""
    if not value:
        return 0
    return int(
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )


def _kwargs(market: dict) -> dict:
    return {
        "question": market["question"],
        "criteria": market["criteria"],
        "outcomes": market["outcomes"],
        "source_urls": market["source_urls"],
        "allowed_domains": market["allowed_domains"],
        "close_ts": _to_ts(market["close_at"]),
        "resolution_deadline_ts": _to_ts(market["resolution_deadline_at"]),
        "challenge_window": market["challenge_window"],
        "resolution_mode": market["resolution_mode"],
        "comparator": market["comparator"],
        "threshold": market["threshold"],
        "metric_name": market["metric_name"],
        "window_start_ts": _to_ts(market["window_start_at"]),
        "window_end_ts": _to_ts(market["window_end_at"]),
        "require_citation": market["require_citation"],
        "measurement_json": json.dumps(market.get("measurement", {})),
        "event_urls": market.get("event_urls", []),
        "event_domains": market.get("event_domains", []),
    }


def _create(client, account, contract: str, market: dict, attempts: int = 6):
    for attempt in range(attempts):
        try:
            transaction_hash = client.write_contract(
                contract, "create_market", account=account, kwargs=_kwargs(market)
            )
            receipt = client.wait_for_transaction_receipt(
                transaction_hash, retries=60, interval=10_000
            )
        except Exception as error:  # noqa: BLE001 - the message decides
            if "Rate limit" not in str(error) or attempt == attempts - 1:
                raise
            print("      the network is rate limited, waiting a minute")
            time.sleep(65)
            continue
        if receipt["status_name"] in ("ACCEPTED", "FINALIZED"):
            return True
        print(f"      not accepted: {receipt['status_name']}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network", default="studionet", choices=sorted(CHAINS))
    parser.add_argument("--wallet", default="cite")
    parser.add_argument(
        "--contract",
        default="",
        help="an existing contract to create the markets on (default: deploy one)",
    )
    arguments = parser.parse_args()

    account = load_account(arguments.wallet)
    client = create_client(CHAINS[arguments.network], account=account)
    print(f"wallet  : {arguments.wallet}  {account.address}")

    if arguments.contract:
        contract = arguments.contract
    else:
        code = CONTRACT_PATH.read_text(encoding="utf-8")
        transaction_hash = client.deploy_contract(code=code, account=account)
        receipt = client.wait_for_transaction_receipt(
            transaction_hash, retries=100, interval=3000
        )
        contract = receipt["data"]["contract_address"]
        print(f"contract: {contract}")

    with open(SEED_FILE, "r", encoding="utf-8") as handle:
        markets = json.load(handle)["markets"]

    print(f"creating {len(markets)} markets, about "
          f"{len(markets) * SECONDS_PER_MARKET // 60} minutes\n")

    started = time.time()
    for index, market in enumerate(markets):
        if _create(client, account, contract, market):
            print(f"  {index + 1:>3}/{len(markets)}  {market['id']}")
        else:
            print(f"  {index + 1:>3}/{len(markets)}  {market['id']}  FAILED")
        elapsed = time.time() - started
        if elapsed < SECONDS_PER_MARKET * (index + 1):
            time.sleep(SECONDS_PER_MARKET * (index + 1) - elapsed)

    count = int(client.read_contract(contract, "get_market_count"))
    print(f"\n{count} markets on {contract}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
