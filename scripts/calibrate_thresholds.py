"""Calibrate the seed thresholds from real climatology.

For every city in the registry the script pulls the ERA5 daily maximum for the
same calendar window across a number of past years, one multi location request
per year, and derives the threshold that makes the market interesting: close to
the typical value, so the odds are near even and the market is worth taking.

    python scripts/calibrate_thresholds.py
"""

import json
import statistics
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "markets" / "stations.json"

YEARS = list(range(2016, 2026))
WINDOW_FROM = "12-01"
WINDOW_TO = "12-20"

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"


def fetch(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "cite-calibration"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    cities = registry["cities"]

    latitudes = ",".join(str(city["reanalysis"]["lat"]) for city in cities)
    longitudes = ",".join(str(city["reanalysis"]["lon"]) for city in cities)

    samples: dict[str, list[float]] = {city["city"]: [] for city in cities}

    for year in YEARS:
        url = (
            f"{ARCHIVE}?latitude={latitudes}&longitude={longitudes}"
            f"&start_date={year}-{WINDOW_FROM}&end_date={year}-{WINDOW_TO}"
            "&daily=temperature_2m_max&timezone=auto"
        )
        try:
            data = fetch(url)
        except Exception as error:
            print(f"  {year}: failed ({str(error)[:70]})")
            continue
        entries = data if isinstance(data, list) else [data]
        for city, entry in zip(cities, entries):
            values = entry.get("daily", {}).get("temperature_2m_max") or []
            for value in values:
                if value is not None:
                    samples[city["city"]].append(float(value))
        print(f"  {year}: {len(entries)} locations")

    print()
    print("city            n     mean   p25    p75   threshold")
    for city in cities:
        values = samples[city["city"]]
        if not values:
            print(f"  {city['city']:<14} no data")
            continue
        mean = statistics.fmean(values)
        p25 = statistics.quantiles(values, n=4)[0]
        p75 = statistics.quantiles(values, n=4)[2]
        # The threshold sits a little above the typical value, so the market is
        # close to even rather than a foregone conclusion.
        threshold = int(round((mean + p75) / 2 * 10))
        # The contract stores thresholds as unsigned integers, so a threshold
        # below zero cannot go on chain. The raw value stays in the calibration
        # block because it is the honest statistic, and the chain gets the
        # clamped one, which turns the market into a freezing question.
        chain_threshold = max(0, threshold)
        city["calibration"] = {
            "window": f"{WINDOW_FROM.replace('-', '/')} to {WINDOW_TO.replace('-', '/')}",
            "years": [str(year) for year in YEARS],
            "samples": len(values),
            "mean_tenths": int(round(mean * 10)),
            "p25_tenths": int(round(p25 * 10)),
            "p75_tenths": int(round(p75 * 10)),
            "seed_threshold_tenths": threshold,
            "chain_threshold_tenths": chain_threshold,
        }
        # The calibrated value replaces the hand written one, so the registry
        # has a single source of truth for every threshold.
        city["seed_threshold_tenths"] = chain_threshold
        print(
            f"  {city['city']:<14} {len(values):<5} {mean:6.1f} {p25:6.1f} {p75:6.1f}   "
            f"{chain_threshold / 10:.1f} C"
            + ("  (below zero, clamped to freezing)" if threshold < 0 else "")
        )

    REGISTRY.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    print()
    print(f"registry updated: {REGISTRY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
