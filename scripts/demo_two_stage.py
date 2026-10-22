"""Create and resolve a corrected two stage market on the live network.

The first attempt at the two stage market gave the measurement group a single
source. The measurement group is a corroboration device and needs two
independent publishers, so the market voided with "insufficient independently
verified evidence". This script does it properly: ERA5 and NASA POWER
corroborate the reading, and the NWS alert feed carries the consequence.

    python scripts/demo_two_stage.py
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
CONTRACT = "0xB0295bcBe44271D194Da693BFd6844022F413958"

EVENT_DATE = "2026-10-14"
EVENT_COMPACT = "20261014"
CLOSE_IN_SECONDS = 60




def main() -> int:
    creator = load_account("tester1")
    bettor = load_account("tester2")
    client = create_client(studionet, account=creator)

    now = int(time.time())
    close_ts = now + CLOSE_IN_SECONDS
    deadline_ts = now + 3600

    measurement = {
        "primary_source": 1,
        "scale": 10,
        "metric_source": "measurement",
        "station": "the ERA5 grid cell nearest 40.7794 degrees north, 73.9692 degrees west, served by the Open-Meteo archive API, nearest to CENTRAL PARK (USW00094728)",
        "variable": "daily maximum temperature (temperature_2m_max)",
        "unit": "degrees Celsius",
        "day_boundary": "the local civil day 00:00 to 24:00 in America/New_York",
        "missing_data": "the market is voided if the authoritative source publishes no value for that day",
        "match_terms": [EVENT_DATE, EVENT_COMPACT, "temperature_2m_max", "t2m_max"],
        "event": {
            "publisher": "the US National Weather Service, api.weather.gov",
            "area": "New York State",
            "criteria": "any alert of any type that covers New York State and is in force on the day counts",
            "require_citation": True,
            "match_terms": [EVENT_DATE],
        },
    }

    sources = [
        "https://archive-api.open-meteo.com/v1/archive?latitude=40.7794&longitude=-73.9692"
        f"&start_date={EVENT_DATE}&end_date={EVENT_DATE}"
        "&daily=temperature_2m_max&timezone=America%2FNew_York",
        "https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M_MAX&community=AG"
        f"&longitude=-73.9692&latitude=40.7794&start={EVENT_COMPACT}&end={EVENT_COMPACT}&format=JSON",
    ]
    events = [
        f"https://api.weather.gov/alerts?start={EVENT_DATE}T00:00:00Z"
        f"&end={EVENT_DATE}T23:59:59Z&area=NY"
    ]

    print("==> creating the two stage market")
    tx_hash = client.write_contract(
        address=CONTRACT,
        function_name="create_market",
        account=creator,
        kwargs={
            "question": f"Will New York reach 20.0 degrees Celsius on {EVENT_DATE} and have a National Weather Service warning in force that day?",
            "criteria": "Read the daily maximum temperature for New York from the measurement source and the alerts for New York State from the event source. Resolve Yes only if both are true: the maximum temperature is at least 20.0 degrees Celsius AND at least one alert covers New York State on that day.",
            "outcomes": ["Yes", "No"],
            "source_urls": sources,
            "allowed_domains": [],
            "close_ts": close_ts,
            "resolution_deadline_ts": deadline_ts,
            "challenge_window": 3600,
            "resolution_mode": "choice",
            "comparator": ">=",
            "threshold": 0,
            "metric_name": "",
            "window_start_ts": 0,
            "window_end_ts": 0,
            "require_citation": True,
            "measurement_json": json.dumps(measurement, separators=(",", ":")),
            "event_urls": events,
            "event_domains": ["weather.gov"],
        },
    )
    client.wait_for_transaction_receipt(tx_hash)
    market_id = client.read_contract(CONTRACT, "get_market_count") - 1
    print(f"  market {market_id}  tx={tx_hash}")

    print("==> betting")
    for outcome in (0, 1):
        tx_hash = client.write_contract(
            address=CONTRACT,
            function_name="place_bet",
            account=bettor,
            args=[market_id, outcome],
            value=10 * 10**18,
        )
        client.wait_for_transaction_receipt(tx_hash)
    market = client.read_contract(CONTRACT, "get_market", args=[market_id])
    print(f"  status={market['status']} staked={market['total_staked']}")

    print(f"==> waiting {CLOSE_IN_SECONDS + 15}s for the close")
    time.sleep(CLOSE_IN_SECONDS + 15)

    print("==> resolving")
    tx_hash = client.write_contract(
        address=CONTRACT,
        function_name="resolve_market",
        account=creator,
        args=[market_id],
    )
    print(f"  tx={tx_hash}")
    try:
        receipt = client.wait_for_transaction_receipt(
            tx_hash, retries=300, interval=4000
        )
        print(f"    status: {receipt}")
    except Exception as error:
        # The receipt may still be pending; the state below is what matters.
        print(f"    still pending: {str(error)[:160]}")

    print("==> final state")
    market = client.read_contract(CONTRACT, "get_market", args=[market_id])
    resolution = json.loads(market["resolution"]) if market["resolution"] else {}
    print(f"  status={market['status']} outcome={market['outcome']}")
    print(f"  citations={market['citations_verified']} event_citations={market['event_citations_verified']}")
    print(f"  reasoning: {(resolution.get('reasoning') or '')[:500]}")
    trail = client.read_contract(CONTRACT, "get_citations", args=[market_id])
    for entry in trail["trail"]:
        print(f"  QUOTE {entry['url'][:110]}")
        print(f"        {entry['quote'][:220]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
