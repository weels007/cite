"""Resolve the markets that the demo created, patiently, and report the trail.

    python scripts/resolve_studionet.py

The resolution runs a real consensus round on the network: the leader fetches
the web pages, the validators re-derive the answer and the committee has to
agree. That takes minutes, not seconds, so the receipt wait is generous and
every status transition is printed.
"""

import json
import sys
import time
from pathlib import Path

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wallet import DEFAULT_WALLET, load_account

from genlayer_py import create_client, studionet

WALLET_FOLDER = Path(r"D:\Genlayer-project\weels\wallet")
CONTRACT = "0x00E02cD320768cd8E55ac7C786119F76BD7452BB"

MARKET_IDS = [0, 1, 2]
MARKET_NAMES = [
    "tier1-jakarta-temperature",
    "tier2-nws-alerts-new-york",
    "tier2-nyc-hot-and-warning",
]




def wait(client, tx_hash, label: str, interval: int = 4000, retries: int = 300):
    """Wait for the receipt and print the outcome. The consensus round takes
    minutes, because every validator fetches the web and calls an LLM."""
    try:
        receipt = client.wait_for_transaction_receipt(
            tx_hash, retries=retries, interval=interval
        )
        print(f"      {label}: {receipt}")
        return receipt
    except Exception as error:
        print(f"      {label}: still pending ({str(error)[:120]})")
        return None


def main() -> int:
    creator = load_account("tester1")
    client = create_client(studionet, account=creator)

    count = client.read_contract(CONTRACT, "get_market_count")
    print(f"==> {count} markets on {CONTRACT}")

    print("==> state before resolving")
    for market_id in MARKET_IDS:
        market = client.read_contract(CONTRACT, "get_market", args=[market_id])
        print(
            f"  {MARKET_NAMES[market_id]}: status={market['status']} "
            f"staked={market['total_staked']} deadline={market['resolution_deadline_ts']}"
        )

    print("==> resolving")
    for market_id in MARKET_IDS:
        name = MARKET_NAMES[market_id]
        if client.read_contract(CONTRACT, "get_market", args=[market_id])["status"] not in (
            "open",
            "closed",
        ):
            print(f"  {name}: already {client.read_contract(CONTRACT, 'get_market', args=[market_id])['status']}, skipping")
            continue
        print(f"  {name}")
        tx_hash = client.write_contract(
            address=CONTRACT,
            function_name="resolve_market",
            account=creator,
            args=[market_id],
        )
        print(f"    tx={tx_hash}")
        status = wait(client, tx_hash, name)
        print(f"    final status: {status}")

    print("==> final state")
    for market_id in MARKET_IDS:
        name = MARKET_NAMES[market_id]
        state = client.read_contract(CONTRACT, "get_market", args=[market_id])
        print(f"  {name}")
        print(
            f"    status={state['status']} outcome={state['outcome']} "
            f"confidence={state['confidence']} metric={state['metric_value']}"
        )
        print(
            f"    citations_verified={state['citations_verified']} "
            f"event_citations={state['event_citations_verified']} "
            f"cited_domains={state['cited_domains']}"
        )
        resolution = json.loads(state["resolution"]) if state["resolution"] else {}
        if resolution:
            print(f"    reasoning: {resolution.get('reasoning', '')[:220]}")
        trail = client.read_contract(CONTRACT, "get_citations", args=[market_id])
        for entry in trail["trail"][:4]:
            print(f"    - {entry['url']}")
            print(f"      \"{entry['quote'][:200]}\"")

    accounting = client.read_contract(CONTRACT, "get_accounting")
    print("==> accounting")
    print(
        f"  staked={accounting['total_staked_all']} paid={accounting['paid_out_all']} "
        f"refunded={accounting['refunded_all']} fees={accounting['fees_collected']}"
    )
    print(
        f"  balance={accounting['contract_balance']} expected={accounting['expected_balance']} "
        f"invariant_holds={accounting['invariant_holds']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
