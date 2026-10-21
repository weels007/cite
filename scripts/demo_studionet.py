"""Run the Cite demo against a live network using a wallet from the weels folder.

    python scripts/demo_studionet.py

The script creates three markets, bets on them from a second wallet, waits for
the betting window to close and then resolves them. The event dates are in the
past on purpose, so that the sources really hold data and the resolution can
run right now.

The wallets are read from ``D:\\Genlayer-project\\weels\\wallet`` and nowhere
else. Nothing in that folder is modified.
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

ROOT = Path(__file__).resolve().parents[1]
WALLET_FOLDER = Path(r"D:\Genlayer-project\weels\wallet")

CONTRACT = "0xeA384Ef9a0d8F87314ddb40d58F0183e69E0707b"

CLOSE_IN_SECONDS = 180
RESOLUTION_WINDOW = 3600
CHALLENGE_WINDOW = 3600

# The event day: in the past, so that the sources hold data right now.
EVENT_DATE = "2026-10-14"
EVENT_COMPACT = "20261014"


def resilient(action, label: str, attempts: int = 6):
    """The hosted studio drops connections now and then, so retry."""
    last = None
    for attempt in range(attempts):
        try:
            return action()
        except Exception as error:
            last = error
            wait = 5 * (attempt + 1)
            print(f"    {label} failed ({str(error)[:70]}), retrying in {wait}s")
            time.sleep(wait)
    raise last


def measurement_spec(station: str, variable: str, unit: str, timezone: str) -> dict:
    return {
        "primary_source": 1,
        "scale": 10,
        "metric_source": "measurement",
        "station": station,
        "variable": variable,
        "unit": unit,
        "day_boundary": f"the local civil day 00:00 to 24:00 in {timezone}",
        "missing_data": "the market is voided if the authoritative source publishes no value for that day",
        "match_terms": [EVENT_DATE, EVENT_COMPACT, "temperature_2m_max", "t2m_max"],
        "event_date": EVENT_DATE,
        "event_date_aliases": [EVENT_DATE, EVENT_COMPACT],
    }


def event_spec(publisher: str, area: str, criteria: str) -> dict:
    return {
        "primary_source": 1,
        "scale": 1,
        "metric_source": "event",
        "station": "not applicable, this market measures an official alert feed",
        "variable": "the number of qualifying alerts",
        "unit": "count",
        "day_boundary": f"the UTC day {EVENT_DATE}, exactly as the feed is queried",
        "missing_data": "the market is voided if the alert feed publishes nothing at all",
        "match_terms": [EVENT_DATE],
        "event": {
            "publisher": publisher,
            "area": area,
            "criteria": criteria,
            "require_citation": True,
            "match_terms": [EVENT_DATE],
        },
    }


def era5(lat: float, lon: float, timezone: str) -> str:
    return (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={EVENT_DATE}&end_date={EVENT_DATE}"
        f"&daily=temperature_2m_max&timezone={timezone.replace('/', '%2F')}"
    )


def power(lat: float, lon: float) -> str:
    return (
        "https://power.larc.nasa.gov/api/temporal/daily/point"
        f"?parameters=T2M_MAX&community=AG&longitude={lon}&latitude={lat}"
        f"&start={EVENT_COMPACT}&end={EVENT_COMPACT}&format=JSON"
    )


def nws(area: str) -> str:
    return (
        "https://api.weather.gov/alerts"
        f"?start={EVENT_DATE}T00:00:00Z&end={EVENT_DATE}T23:59:59Z&area={area}"
    )


def build_markets(now: int) -> list:
    close_ts = now + CLOSE_IN_SECONDS
    deadline_ts = now + RESOLUTION_WINDOW

    return [
        {
            "id": "tier1-jakarta-temperature",
            "question": f"Will the maximum temperature in Jakarta on {EVENT_DATE} be at least 33.0 degrees Celsius?",
            "criteria": "Read the daily maximum temperature from the authoritative source. Resolve Yes if it is at least 33.0 degrees Celsius.",
            "source_urls": [era5(-6.125, 106.655, "Asia/Jakarta"), power(-6.125, 106.655)],
            "allowed_domains": [],
            "event_urls": [],
            "event_domains": [],
            "resolution_mode": "metric",
            "comparator": ">=",
            "threshold": 330,
            "metric_name": "daily maximum temperature in tenths of a degree Celsius",
            "measurement": measurement_spec(
                "the ERA5 grid cell nearest 6.125 degrees south, 106.655 degrees east, served by the Open-Meteo archive API, nearest to JAKARTA/OBSERVATORY (ID000096745)",
                "daily maximum temperature (temperature_2m_max)",
                "degrees Celsius",
                "Asia/Jakarta",
            ),
            "close_ts": close_ts,
            "resolution_deadline_ts": deadline_ts,
        },
        {
            "id": "tier2-nws-alerts-new-york",
            "question": f"Will the US National Weather Service have at least one watch, warning or advisory in force for New York State on {EVENT_DATE}?",
            "criteria": "Look for any alert in the National Weather Service feed that covers New York State and is in force on that day. Resolve Yes if there is at least one, No if there is none.",
            "source_urls": [],
            "allowed_domains": [],
            "event_urls": [nws("NY")],
            "event_domains": ["weather.gov"],
            "resolution_mode": "metric",
            "comparator": ">=",
            "threshold": 1,
            "metric_name": "number of National Weather Service alerts covering New York State",
            "measurement": event_spec(
                "the US National Weather Service, api.weather.gov",
                "New York State",
                "any alert of any type that covers New York State and is in force on the day counts",
            ),
            "close_ts": close_ts,
            "resolution_deadline_ts": deadline_ts,
        },
        {
            "id": "tier2-nyc-hot-and-warning",
            "question": f"Will New York reach 20.0 degrees Celsius on {EVENT_DATE} and have a National Weather Service warning in force that day?",
            "criteria": "Read the daily maximum temperature for New York from the measurement source and the alerts for New York State from the event source. Resolve Yes only if both are true: the maximum temperature is at least 20.0 degrees Celsius AND at least one alert covers New York State on that day.",
            "source_urls": [
                era5(40.7794, -73.9692, "America/New_York"),
                power(40.7794, -73.9692),
            ],
            "allowed_domains": [],
            "event_urls": [nws("NY")],
            "event_domains": ["weather.gov"],
            "resolution_mode": "choice",
            "comparator": ">=",
            "threshold": 0,
            "metric_name": "",
            "measurement": {
                **measurement_spec(
                    "the ERA5 grid cell nearest 40.7794 degrees north, 73.9692 degrees west, served by the Open-Meteo archive API, nearest to CENTRAL PARK (USW00094728)",
                    "daily maximum temperature (temperature_2m_max)",
                    "degrees Celsius",
                    "America/New_York",
                ),
                "event": {
                    "publisher": "the US National Weather Service, api.weather.gov",
                    "area": "New York State",
                    "criteria": "any alert of any type that covers New York State and is in force on the day counts",
                    "require_citation": True,
                    "match_terms": [EVENT_DATE],
                },
            },
            "close_ts": close_ts,
            "resolution_deadline_ts": deadline_ts,
        },
    ]


def main() -> int:
    print("==> wallets")
    creator = load_account("tester1")
    bettor = load_account("tester2")

    client = create_client(studionet, account=creator)
    print(f"  network: {studionet.name} (chain {studionet.id})")

    print("==> contract")
    count = client.read_contract(CONTRACT, "get_market_count")
    print(f"  {CONTRACT}, {count} markets already on chain")

    now = int(time.time())
    markets = build_markets(now)

    print("==> creating the markets")
    market_ids = []
    # The contract may already hold markets, so the new ones start after the
    # ones that are already there.
    first_id = client.read_contract(CONTRACT, "get_market_count")
    for market in markets:
        tx_hash = resilient(
            lambda: client.write_contract(
                address=CONTRACT,
                function_name="create_market",
                account=creator,
                kwargs={
                    "question": market["question"],
                    "criteria": market["criteria"],
                    "outcomes": ["Yes", "No"],
                    "source_urls": market["source_urls"],
                    "allowed_domains": market["allowed_domains"],
                    "close_ts": market["close_ts"],
                    "resolution_deadline_ts": market["resolution_deadline_ts"],
                    "challenge_window": CHALLENGE_WINDOW,
                    "resolution_mode": market["resolution_mode"],
                    "comparator": market["comparator"],
                    "threshold": market["threshold"],
                    "metric_name": market["metric_name"],
                    "window_start_ts": 0,
                    "window_end_ts": 0,
                    "require_citation": True,
                    "measurement_json": json.dumps(
                        market["measurement"], separators=(",", ":")
                    ),
                    "event_urls": market["event_urls"],
                    "event_domains": market["event_domains"],
                },
            ),
            "create_market",
        )
        receipt = resilient(
            lambda: client.wait_for_transaction_receipt(tx_hash), "receipt"
        )
        status = receipt.get("status") or receipt.get("execution_result")
        print(f"  [{len(market_ids)}] {market['id']}  tx={tx_hash[:14]}...  {status}")
        market_ids.append(first_id + len(market_ids))

    print("==> betting")
    for market_id in market_ids:
        for outcome in (0, 1):
            tx_hash = resilient(
                lambda: client.write_contract(
                    address=CONTRACT,
                    function_name="place_bet",
                    account=bettor,
                    args=[market_id, outcome],
                    value=10 * 10**18,
                ),
                "place_bet",
            )
            receipt = resilient(
                lambda: client.wait_for_transaction_receipt(tx_hash), "receipt"
            )
            status = receipt.get("status") or receipt.get("execution_result")
            print(f"  market {market_id} outcome {outcome}  {status}")

    print("==> state before the close")
    for market_id in market_ids:
        market = client.read_contract(CONTRACT, "get_market", args=[market_id])
        print(
            f"  market {market_id}: status={market['status']} "
            f"staked={market['total_staked']} pools={market['pools']}"
        )

    wait = CLOSE_IN_SECONDS + 20
    print(f"==> waiting {wait}s for the betting window to close")
    time.sleep(wait)

    print("==> resolving")
    results = {}
    for market_id, market in zip(market_ids, markets):
        print(f"  resolving {market['id']}")
        tx_hash = resilient(
            lambda: client.write_contract(
                address=CONTRACT,
                function_name="resolve_market",
                account=creator,
                args=[market_id],
            ),
            "resolve_market",
        )
        print(f"    tx={tx_hash}")
        try:
            receipt = resilient(
                lambda: client.wait_for_transaction_receipt(
                    tx_hash, retries=300, interval=4000
                ),
                "receipt",
            )
            print(f"    status: {receipt.get('status') or receipt.get('execution_result')}")
        except Exception as error:
            print(f"    still pending: {str(error)[:160]}")
        results[market_id] = market

    print("==> final state")
    for market_id, market in zip(market_ids, markets):
        state = client.read_contract(CONTRACT, "get_market", args=[market_id])
        print(f"  {market['id']}")
        print(f"    status={state['status']} outcome={state['outcome']} "
              f"confidence={state['confidence']} metric={state['metric_value']}")
        print(f"    citations_verified={state['citations_verified']} "
              f"event_citations={state['event_citations_verified']} "
              f"cited_domains={state['cited_domains']}")
        trail = client.read_contract(CONTRACT, "get_citations", args=[market_id])
        for entry in trail["trail"][:3]:
            print(f"    - {entry['url']}")
            print(f"      \"{entry['quote'][:160]}\"")

    accounting = client.read_contract(CONTRACT, "get_accounting")
    print("==> accounting")
    print(f"  staked={accounting['total_staked_all']} paid={accounting['paid_out_all']} "
          f"refunded={accounting['refunded_all']} fees={accounting['fees_collected']}")
    print(f"  balance={accounting['contract_balance']} expected={accounting['expected_balance']} "
          f"invariant_holds={accounting['invariant_holds']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
