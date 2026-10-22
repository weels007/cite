"""Run a tier 2 market on the live network: a real consequence, counted by
the contract from an official registry.

    python scripts/demo_tier2.py
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from genlayer_py import create_client, studionet
from wallet import load_account

CONTRACT = "0xB0295bcBe44271D194Da693BFd6844022F413958"

# A window in the past, so the registry really holds the records.
WINDOW_FROM = "2026-10-01"
WINDOW_TO = "2026-10-20"
GDACS_URL = (
    "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
    f"?fromDate={WINDOW_FROM}&toDate={WINDOW_TO}"
)

MEASUREMENT = {
    "primary_source": 1,
    "scale": 1,
    "metric_source": "event",
    "station": "not applicable, this market measures the GDACS global disaster registry",
    "variable": "the number of qualifying disaster records",
    "unit": "count",
    "day_boundary": "the from and to dates of the record",
    "missing_data": "the market is voided if the registry answers with nothing at all",
    "match_terms": [WINDOW_FROM[:7]],
    "event": {
        "publisher": "GDACS, the Joint Research Centre of the European Commission",
        "area": "Australia",
        "criteria": "a record counts when it lists Australia among the affected countries and when its alert level is orange or red",
        "require_citation": True,
        "match_terms": [WINDOW_FROM[:7]],
        "count_rules": {
            "alertlevel": ["Orange", "Red"],
            "affected_iso3": ["AUS"],
        },
    },
}


def main() -> int:
    creator = load_account("tester1")
    bettor = load_account("tester2")
    client = create_client(studionet, account=creator)

    now = int(time.time())
    close_ts = now + 120
    deadline_ts = now + 3600

    print("==> creating the tier 2 market")
    tx = client.write_contract(
        address=CONTRACT,
        function_name="create_market",
        account=creator,
        kwargs={
            "question": (
                f"Will GDACS record at least 1 orange or red disaster event "
                f"affecting Australia between {WINDOW_FROM} and {WINDOW_TO}?"
            ),
            "criteria": (
                "Count the records in the Global Disaster Alert and Coordination "
                "System that list Australia among the countries they affected and "
                "that are orange or red. Resolve Yes if the count is at least 1."
            ),
            "outcomes": ["Yes", "No"],
            "source_urls": [],
            "allowed_domains": [],
            "event_urls": [GDACS_URL],
            "event_domains": ["gdacs.org"],
            "close_ts": close_ts,
            "resolution_deadline_ts": deadline_ts,
            "challenge_window": 3600,
            "resolution_mode": "metric",
            "comparator": ">=",
            "threshold": 1,
            "metric_name": "number of orange or red disaster events affecting Australia",
            "window_start_ts": 0,
            "window_end_ts": 0,
            "require_citation": True,
            "measurement_json": json.dumps(MEASUREMENT, separators=(",", ":")),
        },
    )
    receipt = client.wait_for_transaction_receipt(tx)
    market_id = client.read_contract(CONTRACT, "get_market_count") - 1
    print(f"  market {market_id}  tx={tx[:14]}...")

    print("==> betting both sides")
    for outcome in (0, 1):
        client.wait_for_transaction_receipt(
            client.write_contract(
                address=CONTRACT,
                function_name="place_bet",
                account=bettor,
                args=[market_id, outcome],
                value=10 * 10**18,
            )
        )
    market = client.read_contract(CONTRACT, "get_market", args=[market_id])
    print(f"  status={market['status']} staked={market['total_staked']}")

    print("==> waiting for the close")
    time.sleep(max(0, close_ts - int(time.time())) + 20)

    print("==> resolving")
    tx = client.write_contract(
        address=CONTRACT,
        function_name="resolve_market",
        account=creator,
        args=[market_id],
    )
    try:
        receipt = client.wait_for_transaction_receipt(tx, retries=300, interval=4000)
        print(f"  status: {receipt.get('status') or receipt.get('execution_result')}")
    except Exception as error:
        print(f"  still pending: {str(error)[:160]}")
    time.sleep(5)

    state = client.read_contract(CONTRACT, "get_market", args=[market_id])
    print("==> the settlement")
    print(f"  status={state['status']} outcome={state['outcome']} "
          f"confidence={state['confidence']} metric={state['metric_value']}")
    print(f"  citations={state['citations_verified']} "
          f"event_citations={state['event_citations_verified']} "
          f"domains={state['cited_domains']}")

    resolution = json.loads(state["resolution"]) if state["resolution"] else {}
    consensus = resolution.get("consensus", {})
    leader = resolution.get("leader_reading", {})
    print(f"  consensus: {json.dumps(consensus)}")
    print(f"  leader   : {leader.get('reasoning', '')[:400]}")

    trail = client.read_contract(CONTRACT, "get_citations", args=[market_id])
    for entry in trail["trail"][:3]:
        print(f"  QUOTE {entry['url'][:100]}")
        print(f"        {entry['quote'][:220]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
