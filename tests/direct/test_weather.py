"""Weather markets: the locked measurement specification.

A weather market is only correct if it says *exactly* what is measured:
which station, which variable, which unit, which day boundary and which
publisher is authoritative. These tests pin that behaviour down.
"""

import json

from conftest import (
    GEN,
    HOUR,
    QUOTE,
    WEATHER_QUOTE,
    RESOLUTION_PROMPT,
    bet,
    create_market,
    deploy,
    mock_metric_llm,
    mock_sources,
    now_ts,
    warp_to,
)

# The two independent publishers used by the weather markets.
PRIMARY_URL = (
    "https://archive-api.open-meteo.com/v1/archive?latitude=-6.125&longitude=106.655"
    "&start_date=2026-12-01&end_date=2026-12-01"
    "&daily=temperature_2m_max&timezone=Asia%2FJakarta"
)
CORROBORATION_URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M_MAX"
    "&community=AG&longitude=106.655&latitude=-6.125"
    "&start=20261201&end=20261201&format=JSON"
)

MEASUREMENT = {
    "primary_source": 1,
    "scale": 10,
    "station": "the ERA5 grid cell nearest 6.125S 106.655E",
    "variable": "daily maximum temperature",
    "unit": "degrees Celsius",
    "day_boundary": "the local civil day in Asia/Jakarta",
    "missing_data": "void the market",
}


def _weather_market(contract, direct_vm, alice, bob, **kwargs):
    direct_vm.sender = alice
    market_id = create_market(
        contract,
        question="Will the maximum temperature in Jakarta on 1 December 2026 be at least 35.0 C?",
        criteria=(
            "Read the daily maximum temperature from the authoritative source. "
            "Resolve Yes if it is at least 35.0 degrees Celsius."
        ),
        sources=(PRIMARY_URL, CORROBORATION_URL),
        resolution_mode="metric",
        comparator=">=",
        threshold=350,
        metric_name="daily maximum temperature in tenths of a degree Celsius",
        measurement=MEASUREMENT,
        **kwargs,
    )
    bet(contract, direct_vm, bob, market_id, 0, 100 * GEN)
    bet(contract, direct_vm, bob, market_id, 1, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)
    return market_id


def _mock_weather(direct_vm, body: str = WEATHER_QUOTE) -> None:
    direct_vm.mock_web(r"archive-api\.open-meteo\.com", {"status": 200, "body": body})
    direct_vm.mock_web(r"power\.larc\.nasa\.gov", {"status": 200, "body": body})


# ---------------------------------------------------------------------------
# the metric is copied, never calculated
# ---------------------------------------------------------------------------


def test_the_model_copies_the_value_and_the_contract_scales_it(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """33.4 degrees becomes 334 tenths, computed by the contract."""
    contract = deploy(direct_deploy)
    market_id = _weather_market(contract, direct_vm, direct_alice, direct_bob)

    _mock_weather(direct_vm)
    direct_vm.mock_llm(
        RESOLUTION_PROMPT,
        json.dumps(
            {
                "metric": "33.4",
                "confidence": 90,
                "reasoning": "the source prints 33.4",
                "citations": [{"source_index": 1, "quote": WEATHER_QUOTE}],
            }
        ),
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["leader_reading"]["metric"] == 334
    assert result["consensus"]["outcome_index"] == 1  # 334 < 350, so No
    assert contract.get_market(market_id)["metric_value"] == 334


def test_the_value_is_scaled_and_the_threshold_crossed(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _weather_market(contract, direct_vm, direct_alice, direct_bob)

    _mock_weather(direct_vm)
    direct_vm.mock_llm(
        RESOLUTION_PROMPT,
        json.dumps(
            {
                "metric": "35.6",
                "confidence": 90,
                "reasoning": "the source prints 35.6",
                "citations": [{"source_index": 1, "quote": WEATHER_QUOTE}],
            }
        ),
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["leader_reading"]["metric"] == 356
    assert result["consensus"]["outcome_index"] == 0  # 356 >= 350, so Yes
    assert contract.get_market(market_id)["outcome"] == 0


def test_an_integer_source_needs_no_scaling(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """GHCN prints tenths already, so the scale is 1."""
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(
        contract,
        question="Will the maximum temperature at the Jakarta observatory be at least 35.0 C?",
        criteria="Read the daily maximum temperature from the authoritative source.",
        sources=(
            "https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries"
            "&stations=ID000096745&startDate=2026-12-01&endDate=2026-12-01"
            "&dataTypes=TMAX&format=json",
            "https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries"
            "&stations=IDM00096749&startDate=2026-12-01&endDate=2026-12-01"
            "&dataTypes=TMAX&format=json",
        ),
        resolution_mode="metric",
        comparator=">=",
        threshold=350,
        metric_name="daily maximum temperature in tenths of a degree Celsius",
        measurement={
            "primary_source": 1,
            "scale": 1,
            "station": "GHCN-Daily station ID000096745 (JAKARTA/OBSERVATORY, 8 m)",
            "variable": "TMAX",
            "unit": "tenths of a degree Celsius",
        },
    )
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    direct_vm.mock_web(r"ncei\.noaa\.gov", {"status": 200, "body": WEATHER_QUOTE})
    direct_vm.mock_llm(
        RESOLUTION_PROMPT,
        json.dumps(
            {
                "metric": "356",
                "confidence": 90,
                "reasoning": "the source prints 356",
                "citations": [{"source_index": 1, "quote": WEATHER_QUOTE}],
            }
        ),
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["leader_reading"]["metric"] == 356
    assert result["consensus"]["outcome_index"] == 0


# ---------------------------------------------------------------------------
# the authoritative source
# ---------------------------------------------------------------------------


def test_a_value_cited_from_the_wrong_source_does_not_settle(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """The market says source 1 is authoritative, so source 2 cannot provide it."""
    contract = deploy(direct_deploy)
    market_id = _weather_market(contract, direct_vm, direct_alice, direct_bob)

    _mock_weather(direct_vm)
    direct_vm.mock_llm(
        RESOLUTION_PROMPT,
        json.dumps(
            {
                "metric": "33.4",
                "confidence": 90,
                "reasoning": "read from the second source",
                "citations": [{"source_index": 2, "quote": WEATHER_QUOTE}],
            }
        ),
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["consensus"]["resolved"] is False
    assert result["leader_reading"]["cited_primary_source"] is False
    assert contract.get_market(market_id)["status"] == "voided"


def test_a_market_in_another_language_still_finds_its_page(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """The keyword gate only understands English, the match terms do not.

    Without the match terms the page would be dropped and the market would
    void, even though the page holds the right reading.
    """
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(
        contract,
        question=(
            "Apakah suhu maksimum di Jakarta pada 14 Desember 2026 mencapai "
            "setidaknya 33 derajat Celsius?"
        ),
        criteria=(
            "Baca suhu maksimum harian dari sumber otoritatif. "
            "Selesaikan Ya bila NILainya sekurang-kurangnya 33 derajat Celsius."
        ),
        sources=(PRIMARY_URL, CORROBORATION_URL),
        resolution_mode="metric",
        comparator=">=",
        threshold=330,
        metric_name="suhu maksimum harian dalam sepuluh derajat Celsius",
        measurement={
            **MEASUREMENT,
            "match_terms": ["2026-12-14", "temperature_2m_max"],
        },
    )
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    _mock_weather(direct_vm)
    direct_vm.mock_llm(
        RESOLUTION_PROMPT,
        json.dumps(
            {
                "metric": "33.4",
                "confidence": 90,
                "reasoning": "sumber mencantumkan 33.4",
                "citations": [{"source_index": 1, "quote": WEATHER_QUOTE}],
            }
        ),
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["consensus"]["resolved"] is True
    assert result["leader_reading"]["metric"] == 334
    assert result["consensus"]["outcome_index"] == 0


def test_the_station_registry_is_internally_consistent():
    """The registry is the source of truth for every city on the board."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    registry = json.loads((root / "markets" / "stations.json").read_text(encoding="utf-8"))
    cities = registry["cities"]

    assert len(cities) >= 15
    country_codes = set()
    for city in cities:
        assert city["city"] and city["country"] and city["country_name"]
        country_codes.add(city["country"])

        station = city["canonical_station"]
        assert station["ghcn_id"]
        assert station["name"]
        assert -90 <= station["lat"] <= 90
        assert -180 <= station["lon"] <= 180
        assert "elevation_m" in station

        reanalysis = city["reanalysis"]
        assert -90 <= reanalysis["lat"] <= 90
        assert -180 <= reanalysis["lon"] <= 180
        # A timezone that exists, in the IANA form the archive API expects.
        assert "/" in reanalysis["timezone"]
        assert reanalysis["timezone"].count("/") == 1

        assert len(city["observed"]) == 5
        assert all(0 < value < 60 for value in city["observed"])
        assert city["seed_threshold_tenths"] >= 0

    # The board has to span more than one continent.
    assert len(country_codes) >= 10


def test_the_generated_board_matches_the_registry():
    """Every generated market has to point at a city in the registry."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    registry = json.loads((root / "markets" / "stations.json").read_text(encoding="utf-8"))
    board = json.loads((root / "markets" / "seed_markets.json").read_text(encoding="utf-8"))
    cities = {city["city"] for city in registry["cities"]}

    assert board["target_date"]
    assert len(board["markets"]) >= 30

    tier2 = 0
    for market in board["markets"]:
        measurement = market["measurement"]
        assert measurement["primary_source"] >= 1
        assert measurement["scale"] in (1, 10)
        # The language independent escape hatch has to be present, otherwise a
        # market whose question is not in English would never find its page.
        assert measurement["match_terms"]
        assert market["require_citation"] is True
        for url in market["source_urls"]:
            assert url.startswith("https://")
            # The measurement sources are date parameterised APIs.
            assert "2026-12-14" in url or "20261214" in url
        for url in market.get("event_urls", []):
            assert url.startswith("https://")

        event_urls = market.get("event_urls", [])
        if event_urls:
            tier2 += 1
            assert market.get("event_domains")
            assert measurement["event"]["criteria"].strip()
            assert measurement["event"]["match_terms"]
            assert measurement["metric_source"] in ("measurement", "event")
        else:
            city_names = [
                name for name in cities if name.lower().replace(" ", "-") in market["id"]
            ]
            assert city_names, market["id"]

    assert tier2 >= 3


def test_the_measurement_spec_is_kept_on_the_market(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = _weather_market(contract, direct_vm, direct_alice, direct_bob)

    stored = contract.get_market(market_id)
    assert stored["measurement"]["primary_source"] == 1
    assert stored["measurement"]["scale"] == 10
    assert stored["measurement"]["station"].startswith("the ERA5 grid cell")


def test_the_primary_source_must_point_at_a_real_source(
    direct_vm, direct_deploy, direct_alice
):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("primary_source must point at one of the sources"):
        create_market(
            contract,
            measurement={"primary_source": 7, "scale": 10},
        )


def test_the_measurement_spec_must_be_valid_json(direct_vm, direct_deploy, direct_alice):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("the measurement spec is not JSON"):
        contract.create_market(
            question="Will the maximum temperature in Jakarta reach 35 degrees?",
            criteria="Read it from the authoritative source.",
            outcomes=["Yes", "No"],
            source_urls=[PRIMARY_URL, CORROBORATION_URL],
            allowed_domains=[],
            close_ts=now_ts() + HOUR,
            resolution_deadline_ts=now_ts() + 2 * HOUR,
            challenge_window=HOUR,
            resolution_mode="metric",
            comparator=">=",
            threshold=350,
            metric_name="daily maximum temperature",
            window_start_ts=0,
            window_end_ts=0,
            require_citation=True,
            measurement_json="not json at all",
            event_urls=[],
            event_domains=[],
        )


def test_the_scale_must_be_a_positive_integer(direct_vm, direct_deploy, direct_alice):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("scale must be a positive integer"):
        create_market(contract, measurement={"primary_source": 1, "scale": 0})


def test_a_market_without_a_measurement_spec_still_works(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """Non weather markets are unaffected by the new field."""
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(
        contract,
        resolution_mode="metric",
        comparator=">=",
        threshold=10,
        metric_name="events",
    )
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    mock_sources(direct_vm)
    mock_metric_llm(direct_vm, metric=12, quote=WEATHER_QUOTE)

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["consensus"]["resolved"] is True
    assert result["consensus"]["outcome_index"] == 0
    assert contract.get_market(market_id)["measurement"] == {}
