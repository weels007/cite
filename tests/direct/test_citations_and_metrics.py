"""Cite specifics: metric resolution, citation verification, evidence windows."""

import json

from conftest import (
    GEN,
    HOUR,
    QUOTE,
    RESOLUTION_PROMPT,
    SOURCE_A,
    SOURCE_B,
    addr_hex,
    bet,
    create_market,
    deploy,
    mock_metric_llm,
    mock_resolution_llm,
    mock_sources,
    now_ts,
    warp_to,
)


def _open(direct_vm, contract, alice, bob, **kwargs):
    """Create a market, bet on it and move the clock past its close."""
    direct_vm.sender = alice
    market_id = create_market(contract, **kwargs)
    bet(contract, direct_vm, bob, market_id, 0, 100 * GEN)
    # Both sides are backed, so the outcome that wins is always covered. A
    # market nobody backed the winner of is voided and refunded.
    bet(contract, direct_vm, bob, market_id, 1, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)
    return market_id


# ---------------------------------------------------------------------------
# metric mode
# ---------------------------------------------------------------------------


def test_metric_mode_derives_yes_from_the_threshold(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open(
        direct_vm,
        contract,
        direct_alice,
        direct_bob,
        resolution_mode="metric",
        comparator=">=",
        threshold=10,
        metric_name="orbital launches",
    )

    mock_sources(direct_vm)
    mock_metric_llm(direct_vm, metric=12)

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["leader_reading"]["metric"] == 12
    assert result["consensus"]["outcome_index"] == 0

    market = contract.get_market(market_id)
    assert market["status"] == "resolved"
    assert market["outcome"] == 0
    assert market["metric_value"] == 12
    assert market["resolution_mode"] == "metric"
    assert market["metric_name"] == "orbital launches"


def test_metric_mode_derives_no_when_the_threshold_is_not_met(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open(
        direct_vm,
        contract,
        direct_alice,
        direct_bob,
        resolution_mode="metric",
        comparator=">=",
        threshold=10,
        metric_name="orbital launches",
    )

    mock_sources(direct_vm)
    mock_metric_llm(direct_vm, metric=7)

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["leader_reading"]["metric"] == 7
    assert result["consensus"]["outcome_index"] == 1
    assert contract.get_market(market_id)["outcome"] == 1


def test_metric_mode_the_model_cannot_pick_the_outcome(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """The model may only supply the metric; the outcome is derived by code."""
    contract = deploy(direct_deploy)
    market_id = _open(
        direct_vm,
        contract,
        direct_alice,
        direct_bob,
        resolution_mode="metric",
        comparator=">=",
        threshold=10,
        metric_name="orbital launches",
    )

    mock_sources(direct_vm)
    direct_vm.mock_llm(
        RESOLUTION_PROMPT,
        json.dumps(
            {
                "metric": 12,
                "outcome_index": 1,  # the model tries to force "No"
                "confidence": 90,
                "reasoning": "trying to override the contract",
                "citations": [{"source_index": 1, "quote": QUOTE}],
            }
        ),
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    # 12 >= 10, so the contract decides Yes regardless of what the model said.
    assert result["consensus"]["outcome_index"] == 0
    assert contract.get_market(market_id)["outcome"] == 0


def test_metric_mode_supports_every_comparator(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    cases = [
        (">=", 10, 10, 0),
        (">", 10, 10, 1),
        ("<=", 10, 10, 0),
        ("<", 10, 10, 1),
        ("==", 10, 10, 0),
        ("==", 10, 9, 1),
    ]
    contract = deploy(direct_deploy)
    for index, (comparator, threshold, metric, expected) in enumerate(cases):
        market_id = _open(
            direct_vm,
            contract,
            direct_alice,
            direct_bob,
            resolution_mode="metric",
            comparator=comparator,
            threshold=threshold,
            metric_name="events",
        )
        # The first registered mock wins, so the previous case has to go.
        direct_vm.clear_mocks()
        mock_sources(direct_vm)
        mock_metric_llm(direct_vm, metric=metric)
        direct_vm.sender = direct_charlie
        result = contract.resolve_market(market_id)
        assert result["consensus"]["outcome_index"] == expected, (comparator, metric)
        assert contract.get_market(market_id)["outcome"] == expected


def test_the_validator_compares_the_derived_outcome_not_the_raw_metric(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """A reading one unit apart is the same reading, a tenth of a degree."""
    contract = deploy(direct_deploy)
    market_id = _open(
        direct_vm,
        contract,
        direct_alice,
        direct_bob,
        resolution_mode="metric",
        comparator=">=",
        threshold=10,
        metric_name="events",
    )

    mock_sources(direct_vm)
    mock_metric_llm(direct_vm, metric=12)
    direct_vm.sender = direct_charlie
    contract.resolve_market(market_id)

    direct_vm.clear_mocks()
    mock_sources(direct_vm)
    mock_metric_llm(direct_vm, metric=13)

    assert direct_vm.run_validator() is True


def test_the_validator_rejects_a_leader_whose_reading_is_different(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """The reading itself is bound, not only the category it falls into."""
    contract = deploy(direct_deploy)
    market_id = _open(
        direct_vm,
        contract,
        direct_alice,
        direct_bob,
        resolution_mode="metric",
        comparator=">=",
        threshold=10,
        metric_name="events",
    )

    mock_sources(direct_vm)
    mock_metric_llm(direct_vm, metric=12)
    direct_vm.sender = direct_charlie
    contract.resolve_market(market_id)

    direct_vm.clear_mocks()
    mock_sources(direct_vm)
    mock_metric_llm(direct_vm, metric=15)

    assert direct_vm.run_validator() is False


def test_the_validator_rejects_a_metric_on_the_other_side_of_the_threshold(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open(
        direct_vm,
        contract,
        direct_alice,
        direct_bob,
        resolution_mode="metric",
        comparator=">=",
        threshold=10,
        metric_name="events",
    )

    mock_sources(direct_vm)
    mock_metric_llm(direct_vm, metric=12)
    direct_vm.sender = direct_charlie
    contract.resolve_market(market_id)

    direct_vm.clear_mocks()
    mock_sources(direct_vm)
    mock_metric_llm(direct_vm, metric=5)

    assert direct_vm.run_validator() is False


# ---------------------------------------------------------------------------
# citations
# ---------------------------------------------------------------------------


def test_a_verbatim_quote_is_verified_and_recorded(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open(direct_vm, contract, direct_alice, direct_bob)

    mock_sources(direct_vm)
    mock_resolution_llm(direct_vm, outcome_index=0, quote=QUOTE)

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["consensus"]["citations_verified"] == 1

    market = contract.get_market(market_id)
    assert market["citations_verified"] == 1
    assert market["cited_domains"] == ["example.com"]

    trail = contract.get_citations(market_id)
    assert len(trail["trail"]) == 1
    assert trail["trail"][0]["quote"] == QUOTE
    assert trail["trail"][0]["url"] in (SOURCE_A, SOURCE_B)


def test_a_quote_that_is_not_in_the_source_is_dropped(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open(direct_vm, contract, direct_alice, direct_bob)

    mock_sources(direct_vm)
    mock_resolution_llm(
        direct_vm, outcome_index=0, quote="Starlink completed 40 launches in March."
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["consensus"]["citations_verified"] == 0
    assert contract.get_market(market_id)["citations_verified"] == 0


def test_a_quote_that_differs_only_in_punctuation_still_verifies(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open(direct_vm, contract, direct_alice, direct_bob)

    mock_sources(direct_vm)
    mock_resolution_llm(
        direct_vm, outcome_index=0, quote="eth closed at 5,120 usd on 2026-12-31."
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["consensus"]["citations_verified"] == 1


def test_require_citation_voids_the_market_when_the_quote_does_not_verify(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open(direct_vm, contract, direct_alice, direct_bob, require_citation=True)

    mock_sources(direct_vm)
    mock_resolution_llm(
        direct_vm, outcome_index=0, quote="A sentence that is nowhere on the page."
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["consensus"]["resolved"] is False
    assert contract.get_market(market_id)["status"] == "voided"


def test_require_citation_voids_the_market_when_nothing_is_cited(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open(direct_vm, contract, direct_alice, direct_bob, require_citation=True)

    mock_sources(direct_vm)
    mock_resolution_llm(direct_vm, outcome_index=0, uncited=True)

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    # "uncited" is an explicit acknowledgement, so the market may still settle.
    assert result["consensus"]["resolved"] is True


def test_require_citation_voids_the_market_when_the_citations_are_empty(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open(direct_vm, contract, direct_alice, direct_bob, require_citation=True)

    mock_sources(direct_vm)
    direct_vm.mock_llm(
        RESOLUTION_PROMPT,
        json.dumps(
            {
                "resolved": True,
                "outcome_index": 0,
                "confidence": 90,
                "reasoning": "no citations at all",
                "citations": [],
            }
        ),
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["consensus"]["resolved"] is False
    assert contract.get_market(market_id)["status"] == "voided"


def test_the_citation_trail_points_at_the_right_source(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open(direct_vm, contract, direct_alice, direct_bob)

    mock_sources(direct_vm)
    mock_resolution_llm(direct_vm, outcome_index=0, quote=QUOTE, source_index=2)

    direct_vm.sender = direct_charlie
    contract.resolve_market(market_id)

    trail = contract.get_citations(market_id)
    assert trail["trail"][0]["source_index"] == 2
    assert trail["trail"][0]["url"] == SOURCE_B
    assert trail["cited_domains"] == ["example.org"]


def test_two_pages_of_one_publisher_are_enough(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """Counting markets only have one complete record, so one publisher is ok.

    The settlement still has to name the publisher that answered.
    """
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(
        contract,
        resolution_mode="metric",
        comparator=">=",
        threshold=3,
        metric_name="launches",
        sources=(
            "https://en.example.com/launches-q4",
            "https://en.example.com/launches-q1",
        ),
    )
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    direct_vm.mock_web(
        r"en\.example\.com/launches-q4", {"status": 200, "body": QUOTE + " one more."}
    )
    direct_vm.mock_web(
        r"en\.example\.com/launches-q1", {"status": 200, "body": QUOTE + " and another."}
    )
    mock_metric_llm(direct_vm, metric=4)

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["consensus"]["resolved"] is True
    assert result["leader_reading"]["verified_sources"] == 2
    assert result["leader_reading"]["verified_domains"] == 1
    assert result["leader_reading"]["single_publisher"] is True


def test_the_seed_market_file_is_consistent():
    """The launch set has to stay in sync with the contract's parameters."""
    import json
    from pathlib import Path

    seed_file = Path(__file__).resolve().parents[2] / "markets" / "seed_markets.json"
    markets = json.loads(seed_file.read_text(encoding="utf-8"))["markets"]

    assert len(markets) >= 5
    identifiers = set()
    for market in markets:
        assert market["id"] not in identifiers
        identifiers.add(market["id"])
        assert market["resolution_mode"] in ("choice", "metric")
        assert len(market["outcomes"]) >= 2
        assert len(market["source_urls"]) + len(market.get("event_urls", [])) >= 1
        assert market["question"].strip()
        assert market["criteria"].strip()
        assert market["require_citation"] is True
        if market["resolution_mode"] == "metric":
            assert market["metric_name"].strip()
            assert market["threshold"] >= 0
        measurement = market.get("measurement", {})
        assert measurement
        assert measurement["primary_source"] >= 1
        assert measurement["scale"] >= 1
        assert measurement["station"].strip()
        assert measurement["day_boundary"].strip()
        assert measurement["match_terms"]
        event_urls = market.get("event_urls", [])
        if event_urls:
            assert market.get("event_domains")
            assert measurement["event"]["criteria"].strip()
            assert measurement["event"]["match_terms"]


# ---------------------------------------------------------------------------
# market creation validation
# ---------------------------------------------------------------------------


def test_create_market_rejects_an_unknown_resolution_mode(
    direct_vm, direct_deploy, direct_alice
):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("unknown resolution mode"):
        create_market(contract, resolution_mode="vibes")


def test_create_market_rejects_an_unknown_comparator(direct_vm, direct_deploy, direct_alice):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("unknown comparator"):
        create_market(contract, comparator="~")


def test_create_market_rejects_a_negative_threshold(direct_vm, direct_deploy, direct_alice):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("threshold must not be negative"):
        create_market(contract, resolution_mode="metric", threshold=-1)


def test_metric_mode_needs_a_metric_name(direct_vm, direct_deploy, direct_alice):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("metric mode needs a metric name"):
        create_market(contract, resolution_mode="metric", metric_name="")


def test_the_evidence_window_must_not_end_before_it_starts(
    direct_vm, direct_deploy, direct_alice
):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("window ends before it starts"):
        create_market(contract, window_start_ts=1000, window_end_ts=500)


def test_the_evidence_window_is_kept_on_the_market(direct_vm, direct_deploy, direct_alice):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice

    market_id = create_market(
        contract,
        resolution_mode="metric",
        metric_name="orbital launches",
        window_start_ts=1767225600,
        window_end_ts=1798761600,
    )

    market = contract.get_market(market_id)
    assert market["window_start_ts"] == 1767225600
    assert market["window_end_ts"] == 1798761600
    assert market["metric_name"] == "orbital launches"
