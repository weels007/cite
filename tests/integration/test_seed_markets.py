"""The launch board in ``markets/seed_markets.json`` has to be well formed.

The file is the board the frontend shows, and it is the source of the markets
that go on chain. This test checks the file itself, which needs no network
and no deployment.

    pytest tests/integration/test_seed_markets.py -v -s

To put the whole board on chain, use ``scripts/seed_board.py``. It paces the
run below the network's request limit, which is what makes the difference
between a run that finishes and one that does not.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

SEED_FILE = Path(__file__).resolve().parents[2] / "markets" / "seed_markets.json"


def _load_seed_markets() -> list:
    with open(SEED_FILE, "r", encoding="utf-8") as handle:
        return json.load(handle)["markets"]


def _to_ts(value: str) -> int:
    """ISO 8601 -> unix seconds. An empty string means "not set"."""
    if not value:
        return 0
    return int(
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )


def test_the_seed_file_is_valid():
    """Every seed has to carry a resolution shape the contract understands."""
    markets = _load_seed_markets()
    assert len(markets) > 0
    seen = set()
    for market in markets:
        assert market["id"] not in seen
        seen.add(market["id"])
        assert market["resolution_mode"] in ("choice", "metric")
        assert len(market["outcomes"]) >= 2
        # A market is settled from the measurement sources, the event sources,
        # or both. A consequence market has only the second group.
        assert (
            len(market["source_urls"]) + len(market.get("event_urls", [])) >= 1
        ), market["id"]
        assert market["question"].strip()
        assert market["criteria"].strip()
        assert _to_ts(market["close_at"]) > 0
        assert _to_ts(market["resolution_deadline_at"]) > _to_ts(market["close_at"])
        if market["resolution_mode"] == "metric":
            assert market["metric_name"].strip()
            assert market["threshold"] >= 0
        measurement = market.get("measurement", {})
        assert measurement
        assert 1 <= measurement["primary_source"] <= max(
            1, len(market["source_urls"]) + len(market.get("event_urls", []))
        )
        assert measurement["scale"] >= 1
        assert measurement["station"].strip()
        assert measurement["day_boundary"].strip()
        assert measurement["match_terms"]

        event_urls = market.get("event_urls", [])
        event_domains = market.get("event_domains", [])
        if event_urls:
            assert event_domains
            assert "event" in measurement
            assert measurement["event"]["criteria"].strip()
            assert measurement["event"]["match_terms"]
            for url in event_urls:
                assert url.startswith("https://")


def test_every_market_on_the_board_has_a_closing_time():
    """A market without a closing time cannot be traded.

    The consequence markets were written by hand and the measurement markets
    are generated, and the two used to disagree about the name of the field.
    """
    for market in _load_seed_markets():
        assert market.get("close_at"), market["id"]
        assert market.get("resolution_deadline_at"), market["id"]
