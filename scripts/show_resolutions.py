"""Print the full resolution record of every market, including the citations."""

import json
import sys
from pathlib import Path

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wallet import DEFAULT_WALLET, load_account

from genlayer_py import create_client, studionet

WALLET_FOLDER = Path(r"D:\Genlayer-project\weels\wallet")
CONTRACT = "0xB0295bcBe44271D194Da693BFd6844022F413958"
NAMES = [
    "tier1-jakarta-temperature",
    "tier2-nws-alerts-new-york",
    "tier2-nyc-hot-and-warning (under specified, voided)",
    "tier2-nyc-hot-and-warning (corrected)",
]


def main() -> int:
    account = load_account("tester1")
    client = create_client(studionet, account=account)

    for index, name in enumerate(NAMES):
        market = client.read_contract(CONTRACT, "get_market", args=[index])
        resolution = json.loads(market["resolution"]) if market["resolution"] else {}
        print("=" * 78)
        print(f"{index}  {name}")
        print(f"   status       : {market['status']}")
        print(
            f"   outcome      : {market['outcome']}   "
            f"confidence: {market['confidence']}   metric: {market['metric_value']}"
        )
        print(
            f"   citations    : {market['citations_verified']} "
            f"(event: {market['event_citations_verified']})   "
            f"domains: {market['cited_domains']}"
        )
        print(f"   reasoning    : {(resolution.get('reasoning') or '')[:400]}")
        trail = client.read_contract(CONTRACT, "get_citations", args=[index])
        for entry in trail["trail"]:
            print(f"   QUOTE  {entry['url'][:120]}")
            print(f"          {entry['quote'][:260]}")

    accounting = client.read_contract(CONTRACT, "get_accounting")
    print("=" * 78)
    print("accounting")
    print(f"   staked={accounting['total_staked_all']}  paid={accounting['paid_out_all']}")
    print(f"   balance={accounting['contract_balance']}  expected={accounting['expected_balance']}")
    print(f"   invariant_holds={accounting['invariant_holds']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
