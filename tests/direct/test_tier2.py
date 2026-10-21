"""Tier 2 markets: the weather is measurable, the consequence is a judgement.

A tier 2 market reads two evidence groups:

* the **measurement** group, the locked weather facts, and
* the **event** group, the official reports about the consequences.

The contract makes sure the decision rests on the event evidence as well, so a
consequence can never be inferred from a temperature alone.
"""

import json

from conftest import (
    GEN,
    HOUR,
    WEATHER_QUOTE,
    bet,
    create_market,
    deploy,
    now_ts,
    warp_to,
)

MEASUREMENT_URL = (
    "https://archive-api.open-meteo.com/v1/archive?latitude=-6.125&longitude=106.655"
    "&start_date=2026-12-14&end_date=2026-12-14"
    "&daily=temperature_2m_max&timezone=Asia%2FJakarta"
)
MEASUREMENT_URL_B = (
    "https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M_MAX"
    "&community=AG&longitude=106.655&latitude=-6.125"
    "&start=20261214&end=20261214&format=JSON"
)
EVENT_URL = "https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-poland"

MEASUREMENT_QUOTE = "The daily maximum temperature in Jakarta on 2026-12-14 was 33.4 degrees Celsius."
EVENT_QUOTE = "Orange Wind Warning issued for Poland on 2026-12-14 - Malopolskie Province"


def _tier2_market(contract, direct_vm, alice, bob, **kwargs):
    direct_vm.sender = alice
    market_id = create_market(
        contract,
        question="Will Jakarta reach 33.0 degrees Celsius on 14 December 2026?",
        criteria="Read the daily maximum temperature from the authoritative source.",
        sources=(MEASUREMENT_URL, MEASUREMENT_URL_B),
        resolution_mode="metric",
        comparator=">=",
        threshold=330,
        metric_name="daily maximum temperature in tenths of a degree Celsius",
        measurement={
            "primary_source": 1,
            "scale": 10,
            "station": "the ERA5 grid cell nearest 6.125 degrees south, 106.655 degrees east",
            "variable": "daily maximum temperature",
            "unit": "degrees Celsius",
            "day_boundary": "the local civil day in Asia/Jakarta",
            "missing_data": "the market is voided if the source publishes no value",
            "match_terms": ["2026-12-14", "temperature_2m_max"],
        },
        **kwargs,
    )
    bet(contract, direct_vm, bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)
    return market_id


def _mock_both(direct_vm, measurement_body: str = MEASUREMENT_QUOTE, event_body: str = EVENT_QUOTE):
    direct_vm.mock_web(
        r"archive-api\.open-meteo\.com", {"status": 200, "body": measurement_body}
    )
    direct_vm.mock_web(r"feeds\.meteoalarm\.org", {"status": 200, "body": event_body})
    direct_vm.mock_web(r"power\.larc\.nasa\.gov", {"status": 200, "body": measurement_body})


# ---------------------------------------------------------------------------
# the two evidence groups
# ---------------------------------------------------------------------------


def test_the_event_sources_are_stored_on_the_market(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = deploy(direct_deploy)
    market_id = _tier2_market(
        contract,
        direct_vm,
        direct_alice,
        direct_bob,
        event_urls=(EVENT_URL,),
        event_domains=("meteoalarm.org",),
    )

    market = contract.get_market(market_id)
    assert market["event_urls"] == [EVENT_URL]
    assert market["event_domains"] == ["meteoalarm.org"]
    assert market["event_citations_verified"] == 0


def test_a_market_with_only_event_sources_settles_from_the_event_group(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(
        contract,
        question="Will MeteoAlarm record at least 5 orange wind warning areas in Poland?",
        criteria="Count the qualifying entries in the feed.",
        sources=(),
        event_urls=(EVENT_URL,),
        event_domains=("meteoalarm.org",),
        resolution_mode="metric",
        comparator=">=",
        threshold=5,
        metric_name="number of orange wind warning areas",
        measurement={
            "primary_source": 1,
            "scale": 1,
            "metric_source": "event",
            "station": "not applicable",
            "variable": "the number of qualifying entries",
            "unit": "count",
            "day_boundary": "the day the warning becomes effective",
            "missing_data": "the market is voided if the publisher publishes nothing",
            "match_terms": ["2026-12-14"],
            "event": {
                "publisher": "MeteoAlarm",
                "area": "Poland",
                "criteria": "only orange wind warnings count, each area once",
                "require_citation": True,
                "match_terms": ["2026-12-14", "Orange"],
            },
        },
    )
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    direct_vm.mock_web(r"feeds\.meteoalarm\.org", {"status": 200, "body": EVENT_QUOTE})
    direct_vm.mock_llm(
        r"Decide which outcome of the market is true|Answer the market question",
        json.dumps(
            {
                "metric": "6",
                "confidence": 85,
                "reasoning": "counted six qualifying areas",
                "citations": [{"source_index": 1, "quote": EVENT_QUOTE}],
            }
        ),
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["consensus"]["resolved"] is True
    assert result["leader_reading"]["metric"] == 6
    assert result["consensus"]["outcome_index"] == 0
    assert result["consensus"]["event_citations_verified"] == 1
    assert contract.get_market(market_id)["event_citations_verified"] == 1


def test_a_decision_without_event_evidence_does_not_settle(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """A consequence can never be inferred from a temperature alone."""
    contract = deploy(direct_deploy)
    market_id = _tier2_market(
        contract,
        direct_vm,
        direct_alice,
        direct_bob,
        event_urls=(EVENT_URL,),
        event_domains=("meteoalarm.org",),
    )

    _mock_both(direct_vm)
    direct_vm.mock_llm(
        r"Decide which outcome of the market is true|Answer the market question",
        json.dumps(
            {
                "metric": "33.4",
                "confidence": 90,
                "reasoning": "only the measurement was used",
                "citations": [{"source_index": 1, "quote": MEASUREMENT_QUOTE}],
            }
        ),
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["consensus"]["resolved"] is False
    assert result["consensus"]["event_citations_verified"] == 0
    assert contract.get_market(market_id)["status"] == "voided"


def test_a_metric_from_the_event_group_needs_an_event_citation(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """With metric_source=event the value has to come from the event feed."""
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(
        contract,
        question="Will MeteoAlarm record at least 5 orange wind warning areas in Poland?",
        criteria="Count the qualifying entries in the feed.",
        sources=(MEASUREMENT_URL, MEASUREMENT_URL_B),
        event_urls=(EVENT_URL,),
        event_domains=("meteoalarm.org",),
        resolution_mode="metric",
        comparator=">=",
        threshold=5,
        metric_name="number of orange wind warning areas",
        measurement={
            "primary_source": 1,
            "scale": 1,
            "metric_source": "event",
            "station": "not applicable",
            "variable": "the number of qualifying entries",
            "unit": "count",
            "day_boundary": "the day the warning becomes effective",
            "missing_data": "the market is voided if the publisher publishes nothing",
            "match_terms": ["2026-12-14", "temperature_2m_max"],
            "event": {
                "publisher": "MeteoAlarm",
                "area": "Poland",
                "criteria": "only orange wind warnings count",
                "require_citation": True,
                "match_terms": ["2026-12-14", "Orange"],
            },
        },
    )
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    _mock_both(direct_vm)
    direct_vm.mock_llm(
        r"Decide which outcome of the market is true|Answer the market question",
        json.dumps(
            {
                "metric": "6",
                "confidence": 85,
                "reasoning": "the count came from the measurement page",
                "citations": [{"source_index": 1, "quote": MEASUREMENT_QUOTE}],
            }
        ),
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    # The value was not cited from the event feed, so it is not the measurement.
    assert result["consensus"]["resolved"] is False
    assert result["leader_reading"]["cited_primary_source"] is False


def test_the_measurement_still_needs_its_own_source(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """The two groups are checked independently of each other."""
    contract = deploy(direct_deploy)
    market_id = _tier2_market(
        contract,
        direct_vm,
        direct_alice,
        direct_bob,
        event_urls=(EVENT_URL,),
        event_domains=("meteoalarm.org",),
    )

    _mock_both(direct_vm)
    direct_vm.mock_llm(
        r"Decide which outcome of the market is true|Answer the market question",
        json.dumps(
            {
                "metric": "33.4",
                "confidence": 90,
                "reasoning": "the value was taken from the event feed",
                "citations": [{"source_index": 2, "quote": EVENT_QUOTE}],
            }
        ),
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["consensus"]["resolved"] is False
    assert result["leader_reading"]["cited_primary_source"] is False


def test_an_event_source_outside_the_allowlist_is_ignored(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _tier2_market(
        contract,
        direct_vm,
        direct_alice,
        direct_bob,
        event_urls=(EVENT_URL,),
        event_domains=("some-other-publisher.org",),
    )

    _mock_both(direct_vm)
    direct_vm.mock_llm(
        r"Decide which outcome of the market is true|Answer the market question",
        json.dumps(
            {
                "metric": "33.4",
                "confidence": 90,
                "reasoning": "the event feed was not allowed",
                "citations": [{"source_index": 1, "quote": MEASUREMENT_QUOTE}],
            }
        ),
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    # The event source was dropped, so the decision has no event support.
    assert result["consensus"]["resolved"] is False
    assert result["consensus"]["event_citations_verified"] == 0


def test_a_market_without_event_sources_still_works(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """The tier 1 behaviour is unchanged when there is no event group."""
    contract = deploy(direct_deploy)
    market_id = _tier2_market(contract, direct_vm, direct_alice, direct_bob)

    direct_vm.mock_web(
        r"archive-api\.open-meteo\.com", {"status": 200, "body": MEASUREMENT_QUOTE}
    )
    direct_vm.mock_web(
        r"power\.larc\.nasa\.gov", {"status": 200, "body": MEASUREMENT_QUOTE}
    )
    direct_vm.mock_llm(
        r"Decide which outcome of the market is true|Answer the market question",
        json.dumps(
            {
                "metric": "33.4",
                "confidence": 90,
                "reasoning": "the source prints 33.4",
                "citations": [{"source_index": 1, "quote": MEASUREMENT_QUOTE}],
            }
        ),
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["consensus"]["resolved"] is True
    assert result["leader_reading"]["metric"] == 334
    assert result["consensus"]["outcome_index"] == 0
    assert result["consensus"]["event_citations_verified"] == 0
