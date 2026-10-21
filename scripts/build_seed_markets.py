"""Build the launch market board from ``markets/stations.json``.

The registry is the source of truth: it holds the canonical station, the
alternative stations, the reanalysis coordinates, the timezone and a seed
threshold for every city. This script turns it into the market specs that
``create_market`` expects.

    python scripts/build_seed_markets.py

Every generated url was checked against the live service. Note that the ERA5
archive API answers with HTTP 400 for a date that has not happened yet, so
the urls only become readable once the target day is in the past.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "markets" / "stations.json"
OUTPUT = ROOT / "markets" / "seed_markets.json"

# The local day every market measures.
TARGET_DATE = "2026-12-14"
TARGET_COMPACT = "20261214"

# Betting closes before the local day starts everywhere on earth: the latest
# local midnight on the target day is 2026-12-13T10:00Z (UTC+14).
CLOSE_AT = "2026-12-13T09:00:00Z"

# ERA5 needs about five days to publish a day, so give it a comfortable margin.
RESOLUTION_DEADLINE_AT = "2026-12-25T00:00:00Z"
CHALLENGE_WINDOW = 172800

# The terms the source pages are guaranteed to print, whatever the language of
# the market question is.
MATCH_TERMS = [
    TARGET_DATE,
    TARGET_COMPACT,
    "temperature_2m_max",
    "t2m_max",
]

# The day the market is about. The authoritative page has to print it, so a
# source that answers with another day cannot settle the market silently.
EVENT_DATE_ALIASES = [TARGET_DATE, TARGET_COMPACT]


def _to_ts(value) -> int:
    """ISO 8601 to unix seconds. An empty value means 'not set'."""
    if not value:
        return 0
    return int(
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )


def era5_url(lat: float, lon: float, timezone: str, variable: str = "temperature_2m_max") -> str:
    return (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={TARGET_DATE}&end_date={TARGET_DATE}"
        f"&daily={variable}&timezone={quote(timezone, safe='')}"
    )


def power_url(lat: float, lon: float, parameter: str = "T2M_MAX") -> str:
    return (
        "https://power.larc.nasa.gov/api/temporal/daily/point"
        f"?parameters={parameter}&community=AG"
        f"&longitude={lon}&latitude={lat}"
        f"&start={TARGET_COMPACT}&end={TARGET_COMPACT}&format=JSON"
    )


def ghcn_url(station_id: str, variable: str = "TMAX") -> str:
    return (
        "https://www.ncei.noaa.gov/access/services/data/v1"
        "?dataset=daily-summings"
        f"&stations={station_id}"
        f"&startDate={TARGET_DATE}&endDate={TARGET_DATE}"
        f"&dataTypes={quote(variable, safe='')}&format=json"
    )


def build_market(city: dict) -> dict:
    reanalysis = city["reanalysis"]
    station = city["canonical_station"]
    calibration = city.get("calibration", {})
    raw_threshold = calibration.get(
        "seed_threshold_tenths", city["seed_threshold_tenths"]
    )
    threshold = calibration.get("chain_threshold_tenths", max(0, raw_threshold))
    threshold_degrees = threshold / 10.0
    # A threshold below zero cannot be stored in an unsigned integer, and in a
    # cold city the interesting question is not "unusually warm" but "will it
    # reach freezing at all".
    freezing = raw_threshold < 0
    if freezing:
        threshold = 0
        threshold_degrees = 0.0
    question = (
        f"Will the maximum temperature in {city['city']} on {TARGET_DATE} "
        f"reach at least {threshold_degrees:.1f} degrees Celsius?"
    )
    if freezing:
        question = (
            f"Will the maximum temperature in {city['city']} on {TARGET_DATE} "
            f"reach 0.0 degrees Celsius, that is, will it touch freezing?"
        )

    return {
        "id": f"wx-{city['city'].lower().replace(' ', '-')}-tmax-{TARGET_DATE}",
        "shape": "metric",
        "question": question,
        "criteria": (
            "Read the daily maximum temperature from the authoritative source. "
            f"Resolve Yes if it is at least {threshold_degrees:.1f} degrees Celsius."
        ),
        "outcomes": ["Yes", "No"],
        "source_urls": [
            era5_url(reanalysis["lat"], reanalysis["lon"], reanalysis["timezone"]),
            power_url(reanalysis["lat"], reanalysis["lon"]),
        ],
        "allowed_domains": [],
        "close_at": CLOSE_AT,
        "resolution_deadline_at": RESOLUTION_DEADLINE_AT,
        "challenge_window": CHALLENGE_WINDOW,
        "resolution_mode": "metric",
        "comparator": ">=",
        "threshold": threshold,
        "metric_name": "daily maximum temperature in tenths of a degree Celsius",
        "window_start_at": "",
        "window_end_at": "",
        "require_citation": True,
        "measurement": {
            "primary_source": 1,
            "scale": 10,
            "station": (
                f"the ERA5 grid cell nearest {reanalysis['lat']} degrees, "
                f"{reanalysis['lon']} degrees, served by the Open-Meteo archive API, "
                f"nearest to {station['name']} ({station['ghcn_id']})"
            ),
            "variable": "daily maximum temperature (temperature_2m_max)",
            "unit": "degrees Celsius",
            "day_boundary": (
                f"the local civil day 00:00 to 24:00 in {reanalysis['timezone']}"
            ),
            "missing_data": (
                "the market is voided if the authoritative source publishes no value "
                "for that day"
            ),
            "match_terms": MATCH_TERMS,
        "event_date": TARGET_DATE,
        "event_date_aliases": EVENT_DATE_ALIASES,
        },
    }


def build_precipitation_market(city: dict) -> dict:
    reanalysis = city["reanalysis"]
    return {
        "id": f"wx-{city['city'].lower().replace(' ', '-')}-prcp-{TARGET_DATE}",
        "shape": "metric",
        "question": (
            f"Will {city['city']} record at least 20.0 mm of rain on {TARGET_DATE}?"
        ),
        "criteria": (
            "Read the daily total precipitation from the authoritative source. "
            "Resolve Yes if it is at least 20.0 millimetres."
        ),
        "outcomes": ["Yes", "No"],
        "source_urls": [
            era5_url(
                reanalysis["lat"],
                reanalysis["lon"],
                reanalysis["timezone"],
                variable="precipitation_sum",
            ),
            power_url(reanalysis["lat"], reanalysis["lon"], parameter="PRECTOTCORR"),
        ],
        "allowed_domains": [],
        "close_at": CLOSE_AT,
        "resolution_deadline_at": RESOLUTION_DEADLINE_AT,
        "challenge_window": CHALLENGE_WINDOW,
        "resolution_mode": "metric",
        "comparator": ">=",
        "threshold": 200,
        "metric_name": "daily total precipitation in tenths of a millimetre",
        "window_start_at": "",
        "window_end_at": "",
        "require_citation": True,
        "measurement": {
            "primary_source": 1,
            "scale": 10,
            "station": (
                f"the ERA5 grid cell nearest {reanalysis['lat']} degrees, "
                f"{reanalysis['lon']} degrees, served by the Open-Meteo archive API"
            ),
            "variable": "daily total precipitation (precipitation_sum)",
            "unit": "millimetres",
            "day_boundary": (
                f"the local civil day 00:00 to 24:00 in {reanalysis['timezone']}"
            ),
            "missing_data": (
                "the market is voided if the authoritative source publishes no value "
                "for that day"
            ),
            "match_terms": MATCH_TERMS + ["precipitation_sum", "prectotcorr"],
        "event_date": TARGET_DATE,
        "event_date_aliases": EVENT_DATE_ALIASES,
        },
    }


def build_station_market(city: dict) -> dict:
    """The station record flavour, where the national network still publishes."""
    station = city["canonical_station"]
    reanalysis = city["reanalysis"]
    threshold = city["seed_threshold_tenths"]
    threshold_degrees = threshold / 10.0
    return {
        "id": f"wx-{city['city'].lower().replace(' ', '-')}-station-tmax-{TARGET_DATE}",
        "shape": "metric",
        "question": (
            f"Will the maximum temperature recorded at {station['name']} in "
            f"{city['city']} on {TARGET_DATE} be at least {threshold_degrees:.1f} "
            "degrees Celsius?"
        ),
        "criteria": (
            "Read the daily maximum temperature recorded at the station from the "
            f"authoritative source. Resolve Yes if it is at least "
            f"{threshold_degrees:.1f} degrees Celsius."
        ),
        "outcomes": ["Yes", "No"],
        "source_urls": [
            ghcn_url(station["ghcn_id"]),
            era5_url(reanalysis["lat"], reanalysis["lon"], reanalysis["timezone"]),
        ],
        "allowed_domains": [],
        "close_at": CLOSE_AT,
        "resolution_deadline_at": RESOLUTION_DEADLINE_AT,
        "challenge_window": CHALLENGE_WINDOW,
        "resolution_mode": "metric",
        "comparator": ">=",
        "threshold": threshold,
        "metric_name": "daily maximum temperature in tenths of a degree Celsius",
        "window_start_at": "",
        "window_end_at": "",
        "require_citation": True,
        "measurement": {
            "primary_source": 1,
            "scale": 1,
            "station": (
                f"GHCN-Daily station {station['ghcn_id']} ({station['name']}, "
                f"{station['elevation_m']} m)"
            ),
            "variable": "TMAX, the daily maximum temperature, in tenths of a degree Celsius",
            "unit": "tenths of a degree Celsius",
            "day_boundary": (
                f"the local civil day 00:00 to 24:00 in {reanalysis['timezone']}"
            ),
            "missing_data": (
                "the market is voided if the station published no TMAX value for that day"
            ),
            "match_terms": MATCH_TERMS + ["tmax"],
        "event_date": TARGET_DATE,
        "event_date_aliases": EVENT_DATE_ALIASES,
        },
    }


def build_comparison_market(first: dict, second: dict) -> dict:
    a = first["reanalysis"]
    b = second["reanalysis"]
    return {
        "id": f"wx-{first['city'].lower().replace(' ', '-')}-vs-"
        f"{second['city'].lower().replace(' ', '-')}-{TARGET_DATE}",
        "shape": "choice",
        "question": (
            f"Will {first['city']} be hotter than {second['city']} on {TARGET_DATE}?"
        ),
        "criteria": (
            "Read the daily maximum temperature for both cities from their "
            "authoritative sources. Resolve Yes if the first city is strictly "
            "hotter, No otherwise."
        ),
        "outcomes": ["Yes", "No"],
        "source_urls": [
            era5_url(a["lat"], a["lon"], a["timezone"]),
            era5_url(b["lat"], b["lon"], b["timezone"]),
        ],
        "allowed_domains": [],
        "close_at": CLOSE_AT,
        "resolution_deadline_at": RESOLUTION_DEADLINE_AT,
        "challenge_window": CHALLENGE_WINDOW,
        "resolution_mode": "choice",
        "comparator": ">=",
        "threshold": 0,
        "metric_name": "",
        "window_start_at": "",
        "window_end_at": "",
        "require_citation": True,
        "measurement": {
            "primary_source": 1,
            "scale": 10,
            "station": (
                f"the ERA5 grid cells nearest {a['lat']}, {a['lon']} and "
                f"{b['lat']}, {b['lon']}"
            ),
            "variable": "daily maximum temperature (temperature_2m_max)",
            "unit": "degrees Celsius",
            "day_boundary": "the local civil day in each city's own timezone",
            "missing_data": (
                "the market is voided if either source publishes no value for that day"
            ),
            "match_terms": MATCH_TERMS,
        "event_date": TARGET_DATE,
        "event_date_aliases": EVENT_DATE_ALIASES,
        },
    }


def main() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    cities = {city["city"]: city for city in registry["cities"]}

    markets = []
    for city in registry["cities"]:
        markets.append(build_market(city))
        markets.append(build_precipitation_market(city))

    # The station flavour, for the cities whose national network still
    # publishes to GHCN-Daily.
    for name in ("New York", "Sydney", "Cairo"):
        markets.append(build_station_market(cities[name]))

    markets.append(build_comparison_market(cities["Jakarta"], cities["Singapore"]))
    markets.append(build_comparison_market(cities["Berlin"], cities["Moscow"]))

    # The tier 2 markets are hand written: they read an official alert feed
    # instead of a measurement, and they carry an event specification. Their
    # dates are already in the same shape as the generated ones.
    tier2_file = ROOT / "markets" / "tier2_markets.json"
    tier2 = json.loads(tier2_file.read_text(encoding="utf-8"))["markets"]
    for market in tier2:
        market.setdefault("event_urls", [])
        market.setdefault("event_domains", [])
        market.setdefault("window_start_at", "")
        market.setdefault("window_end_at", "")
    markets.extend(tier2)

    OUTPUT.write_text(
        json.dumps(
            {
                "$comment": (
                    "Generated by scripts/build_seed_markets.py from "
                    "markets/stations.json. Do not edit by hand."
                ),
                "target_date": TARGET_DATE,
                "markets": markets,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(markets)} markets to {OUTPUT}")


if __name__ == "__main__":
    main()
