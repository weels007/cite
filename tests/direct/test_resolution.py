"""Resolution: web retrieval, LLM extraction and validator consensus."""

import json

from conftest import (
    CHALLENGE_PROMPT,
    GEN,
    HOUR,
    RESOLUTION_PROMPT,
    bet,
    create_market,
    deploy,
    mock_sources,
    mock_resolution_llm,
    now_ts,
    warp_to,
)


def _open_market_with_bets(contract, direct_vm, direct_alice, direct_bob, **kwargs):
    direct_vm.sender = direct_alice
    market_id = create_market(contract, **kwargs)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, now_ts() + HOUR + 60)
    return market_id


def test_a_source_outside_the_allowlist_is_ignored(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    # Only the first domain is accepted, the second source is discarded even
    # though it answers perfectly.
    market_id = create_market(contract, allowed_domains=("example.com",))
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, now_ts() + HOUR + 60)

    mock_sources(direct_vm)
    mock_resolution_llm(direct_vm, outcome_index=0)

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["leader_reading"]["verified_sources"] == 1
    assert result["leader_reading"]["verified_domains"] == 1
    assert result["consensus"]["resolved"] is False
    assert contract.get_market(market_id)["status"] == "voided"


def test_a_market_can_have_more_than_two_outcomes(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(
        contract,
        question="Will ETH close above 5000 USD on 2026-12-31?",
        outcomes=("Yes", "No", "Maybe"),
    )
    bet(contract, direct_vm, direct_bob, market_id, 2, 100 * GEN)
    warp_to(direct_vm, now_ts() + HOUR + 60)

    mock_sources(direct_vm)
    mock_resolution_llm(direct_vm, outcome_index=2)

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["consensus"]["outcome_index"] == 2
    market = contract.get_market(market_id)
    assert market["outcome"] == 2
    assert market["pools"] == [0, 0, 100 * GEN]


def test_resolve_market_settles_on_the_agreed_outcome(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open_market_with_bets(contract, direct_vm, direct_alice, direct_bob)

    mock_sources(direct_vm)
    mock_resolution_llm(direct_vm, outcome_index=0, confidence=88)

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["consensus"]["resolved"] is True
    assert result["consensus"]["outcome_index"] == 0
    assert result["leader_reading"]["verified_sources"] == 2
    assert result["leader_reading"]["verified_domains"] == 2

    market = contract.get_market(market_id)
    assert market["status"] == "resolved"
    assert market["outcome"] == 0
    assert market["confidence"] == 88
    assert market["resolved_at"] != ""
    # The 1% protocol fee is carved out of the pool at settlement time.
    assert market["fee_wei"] == GEN


def test_resolve_voids_the_market_when_only_one_source_is_available(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open_market_with_bets(contract, direct_vm, direct_alice, direct_bob)

    # Only the first source answers, the second one is unreachable.
    direct_vm.mock_web(
        r"news\.example\.com/eth-outlook",
        {"status": 200, "body": "ETH closed at 5120 USD on 2026-12-31."},
    )
    mock_resolution_llm(direct_vm, outcome_index=0)

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["consensus"]["resolved"] is False
    assert result["leader_reading"]["verified_sources"] == 1
    market = contract.get_market(market_id)
    assert market["status"] == "voided"


def test_resolve_voids_the_market_when_the_committee_is_not_sure(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open_market_with_bets(contract, direct_vm, direct_alice, direct_bob)

    mock_sources(direct_vm)
    direct_vm.mock_llm(
        RESOLUTION_PROMPT,
        json.dumps(
            {
                "resolved": False,
                "outcome_index": -1,
                "confidence": 10,
                "reasoning": "The event has not happened yet.",
            }
        ),
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["consensus"]["resolved"] is False
    assert contract.get_market(market_id)["status"] == "voided"


def test_a_page_that_never_mentions_the_subject_is_discarded(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open_market_with_bets(contract, direct_vm, direct_alice, direct_bob)

    # The second source is about something completely different.
    direct_vm.mock_web(
        r"news\.example\.com/eth-outlook",
        {"status": 200, "body": "ETH closed at 5120 USD on 2026-12-31."},
    )
    direct_vm.mock_web(
        r"data\.example\.org/eth-prices",
        {"status": 200, "body": "Recipe of the day: banana bread with walnuts."},
    )
    mock_resolution_llm(direct_vm, outcome_index=0)

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    assert result["leader_reading"]["verified_sources"] == 1
    assert result["consensus"]["resolved"] is False


def test_the_validator_accepts_a_leader_it_agrees_with(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open_market_with_bets(contract, direct_vm, direct_alice, direct_bob)

    mock_sources(direct_vm)
    mock_resolution_llm(direct_vm, outcome_index=0, confidence=80)

    direct_vm.sender = direct_charlie
    contract.resolve_market(market_id)

    # Re-run the captured validator with the very same evidence.
    assert direct_vm.run_validator() is True


def test_the_validator_rejects_a_leader_that_reads_the_evidence_differently(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open_market_with_bets(contract, direct_vm, direct_alice, direct_bob)

    mock_sources(direct_vm)
    mock_resolution_llm(direct_vm, outcome_index=0, confidence=80)

    direct_vm.sender = direct_charlie
    contract.resolve_market(market_id)

    # The validator now sees evidence that points at the other outcome.
    direct_vm.clear_mocks()
    mock_sources(direct_vm, body="ETH closed at 4100 USD on 2026-12-31.")
    mock_resolution_llm(direct_vm, outcome_index=1, confidence=80)

    assert direct_vm.run_validator() is False


def test_the_validator_rejects_an_overconfident_leader(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open_market_with_bets(contract, direct_vm, direct_alice, direct_bob)

    mock_sources(direct_vm)
    mock_resolution_llm(direct_vm, outcome_index=0, confidence=95)

    direct_vm.sender = direct_charlie
    contract.resolve_market(market_id)

    # Same outcome, but the validator is far less sure about it.
    direct_vm.clear_mocks()
    mock_sources(direct_vm)
    mock_resolution_llm(direct_vm, outcome_index=0, confidence=20)

    assert direct_vm.run_validator() is False


def test_the_validator_tolerates_a_small_confidence_gap(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open_market_with_bets(contract, direct_vm, direct_alice, direct_bob)

    mock_sources(direct_vm)
    mock_resolution_llm(direct_vm, outcome_index=0, confidence=80)

    direct_vm.sender = direct_charlie
    contract.resolve_market(market_id)

    direct_vm.clear_mocks()
    mock_sources(direct_vm)
    mock_resolution_llm(direct_vm, outcome_index=0, confidence=55)

    assert direct_vm.run_validator() is True


def test_resolve_is_rejected_before_the_betting_window_closes(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(contract)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)

    with direct_vm.expect_revert("still open for betting"):
        contract.resolve_market(market_id)


def test_resolve_is_rejected_after_the_resolution_deadline(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(contract, close_in=HOUR, resolution_in=2 * HOUR)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)

    warp_to(direct_vm, now_ts() + 3 * HOUR)

    with direct_vm.expect_revert("resolution deadline has passed"):
        contract.resolve_market(market_id)


def test_resolve_is_rejected_when_nobody_bet(
    direct_vm, direct_deploy, direct_alice, direct_charlie
):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(contract)

    warp_to(direct_vm, now_ts() + HOUR + 60)

    with direct_vm.expect_revert("the market has no bets"):
        contract.resolve_market(market_id)


def test_a_market_cannot_be_resolved_twice(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open_market_with_bets(contract, direct_vm, direct_alice, direct_bob)

    mock_sources(direct_vm)
    mock_resolution_llm(direct_vm, outcome_index=0)

    direct_vm.sender = direct_charlie
    contract.resolve_market(market_id)

    with direct_vm.expect_revert("not resolvable right now"):
        contract.resolve_market(market_id)


def test_a_malformed_llm_answer_is_not_silently_accepted(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _open_market_with_bets(contract, direct_vm, direct_alice, direct_bob)

    mock_sources(direct_vm)
    # The outcome index points outside of the allowed outcomes.
    direct_vm.mock_llm(
        RESOLUTION_PROMPT,
        json.dumps(
            {
                "resolved": True,
                "outcome_index": 7,
                "confidence": 90,
                "reasoning": "nonsense",
            }
        ),
    )

    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("'outcome_index' is out of range"):
        contract.resolve_market(market_id)
