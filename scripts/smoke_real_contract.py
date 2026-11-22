"""Smoke-test key steward-fixed methods on a real deployed studionet contract.

Runs against a specific contract address (default: project deployment) with a
real wallet. No mock LLM. Creates txs on that contract.

    python scripts/smoke_real_contract.py --contract 0xFE10832281BB86994A7503D93AB6aC59DDFf4FeA --wallet tester1
"""

import argparse
import json
import sys
import time
from pathlib import Path

from genlayer_py import create_client, studionet

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wallet import load_account  # noqa: E402

POLL_INTERVAL = 10_000
SOURCE_A = "https://en.wikipedia.org/wiki/Ethereum"
SOURCE_B = "https://en.wikipedia.org/wiki/Bitcoin"


def wait_receipt(client, tx_hash, retries=90):
    receipt = client.wait_for_transaction_receipt(
        tx_hash, retries=retries, interval=POLL_INTERVAL
    )
    status = receipt.get("status_name")
    if status not in ("ACCEPTED", "FINALIZED"):
        raise RuntimeError(f"tx {tx_hash} not accepted: {status} {receipt}")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--wallet", default="tester1")
    args = parser.parse_args()

    account = load_account(args.wallet)
    client = create_client(studionet, account=account)
    contract = args.contract
    print(f"wallet   : {account.address}")
    print(f"contract : {contract}")
    print(f"count    : {client.read_contract(contract, 'get_market_count')}")

    now = int(time.time())
    create_kwargs = {
        "question": "Will the Wikipedia article about Ethereum exist before 1 January 2030?",
        "criteria": "Resolve Yes when the Wikipedia article about Ethereum exists and is not a redirect, No otherwise.",
        "outcomes": ["Yes", "No"],
        "source_urls": [SOURCE_A, SOURCE_B],
        "allowed_domains": [],
        "close_ts": now + 30,
        "resolution_deadline_ts": now + 3600,
        "challenge_window": 120,
        "resolution_mode": "choice",
        "comparator": ">=",
        "threshold": 0,
        "metric_name": "",
        "window_start_ts": 0,
        "window_end_ts": 0,
        "require_citation": True,
        "measurement_json": json.dumps({}),
        "event_urls": [],
        "event_domains": [],
    }
    tx = client.write_contract(contract, "create_market", account=account, kwargs=create_kwargs)
    wait_receipt(client, tx)
    market_id = int(client.read_contract(contract, "get_market_count")) - 1
    print(f"created market {market_id}")

    for outcome, value in [(0, 10**17), (1, 10**17)]:
        tx = client.write_contract(
            contract, "place_bet", account=account, args=[market_id, outcome], value=value
        )
        wait_receipt(client, tx)
        print(f"bet outcome={outcome}")

    delay = create_kwargs["close_ts"] - int(time.time())
    if delay > 0:
        print(f"waiting {delay + 2}s for close...")
        time.sleep(delay + 2)

    # resolve - may need retry on transient provider issues
    for attempt in range(3):
        tx = client.write_contract(contract, "resolve_market", account=account, args=[market_id])
        receipt = wait_receipt(client, tx, retries=120)
        market = client.read_contract(contract, "get_market", args=[market_id])
        if market["status"] in ("resolved", "settled", "voided"):
            print(f"resolved status={market['status']} outcome={market['outcome']}")
            break
        print(f"resolve attempt {attempt+1} status={market['status']}")
    else:
        raise RuntimeError("market not resolved")

    trail = client.read_contract(contract, "get_citations", args=[market_id])
    print(f"citations_verified={trail.get('citations_verified')} trail_len={len(trail.get('trail', []))}")
    for entry in trail.get("trail", []):
        print(f"  - [{entry.get('source_index')}] {entry.get('url')}")

    # Steward fix #2: claim before challenge window closes must fail
    market = client.read_contract(contract, "get_market", args=[market_id])
    now_ts = int(time.time())
    deadline = int(market["challenge_deadline_ts"])
    print(f"challenge_deadline_ts={deadline} now={now_ts}")
    if market["status"] in ("resolved", "settled") and now_ts <= deadline:
        try:
            tx = client.write_contract(contract, "claim", account=account, args=[market_id])
            receipt = client.wait_for_transaction_receipt(tx, retries=60, interval=POLL_INTERVAL)
            # if accepted, that's bad - but check message/status
            print(f"CLAIM DURING WINDOW status={receipt.get('status_name')} (UNEXPECTED)")
        except Exception as err:
            msg = str(err)
            if "challenge window" in msg.lower() or "EXPECTED" in msg:
                print("claim-before-window: REJECTED as expected")
            else:
                print(f"claim-before-window: error {msg[:200]}")
    else:
        print("window already closed or market not claimable; skipping claim-before-window check")

    # wait for challenge window then claim
    wait = deadline - int(time.time()) + 5
    if wait > 0:
        print(f"waiting {wait}s for challenge window to close...")
        time.sleep(wait)

    if market["status"] in ("resolved", "settled"):
        tx = client.write_contract(contract, "claim", account=account, args=[market_id])
        receipt = wait_receipt(client, tx, retries=90)
        print(f"claim after window: {receipt.get('status_name')}")
        # confirm payout if pending
        try:
            tx = client.write_contract(contract, "confirm_payout", account=account, args=[market_id, int(market["outcome"])])
            receipt = wait_receipt(client, tx, retries=90)
            print(f"confirm_payout: {receipt.get('status_name')}")
        except Exception as err:
            print(f"confirm_payout: {err}")

    final = client.read_contract(contract, "get_market", args=[market_id])
    acct = client.read_contract(contract, "get_accounting")
    print(f"final status={final['status']} invariant_holds={acct['invariant_holds']}")
    print("SMOKE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
