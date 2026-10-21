"""The adversarial paths a review of this contract asked for.

* a failed outbound transfer has to leave a recoverable obligation behind
* a market nobody backed the winner of must not take the losing side's money
* the resolution has to be about the day the market was opened for
* the dispute has to be kept with the market
"""

import json

from conftest import (
    GEN,
    HOUR,
    QUOTE,
    RESOLUTION_PROMPT,
    WEATHER_QUOTE,
    bet,
    create_market,
    deploy,
    mock_metric_llm,
    mock_resolution_llm,
    mock_sources,
    now_ts,
    warp_to,
)

MEASUREMENT_URL = (
    "https://archive-api.open-meteo.com/v1/archive?latitude=-6.125&longitude=106.655"
    "&start_date=2026-10-14&end_date=2026-10-14"
    "&daily=temperature_2m_max&timezone=Asia%2FJakarta"
)
POWER_URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M_MAX"
    "&community=AG&longitude=106.655&latitude=-6.125"
    "&start=20261014&end=20261014&format=JSON"
)

MEASUREMENT = {
    "primary_source": 1,
    "scale": 10,
    "metric_source": "measurement",
    "station": "the ERA5 grid cell nearest 6.125 degrees south, 106.655 degrees east",
    "variable": "daily maximum temperature (temperature_2m_max)",
    "unit": "degrees Celsius",
    "day_boundary": "the local civil day 00:00 to 24:00 in Asia/Jakarta",
    "missing_data": "the market is voided if the source publishes no value",
    "match_terms": ["2026-10-14", "temperature_2m_max"],
    "event_date": "2026-10-14",
    "event_date_aliases": ["2026-10-14", "20261014"],
}

DAY_BODY = (
    "2026-10-14 daily maximum temperature 34.6 degrees Celsius. "
    "ETH closed at 5120 USD on 2026-12-31."
)


def _market(contract, direct_vm, alice, bob, **kwargs):
    direct_vm.sender = alice
    market_id = create_market(
        contract,
        question="Will the maximum temperature in Jakarta on 14 October 2026 be at least 33.0 degrees Celsius?",
        criteria="Read the daily maximum temperature from the authoritative source.",
        sources=(MEASUREMENT_URL, POWER_URL),
        resolution_mode="metric",
        comparator=">=",
        threshold=330,
        metric_name="daily maximum temperature in tenths of a degree Celsius",
        measurement=MEASUREMENT,
        **kwargs,
    )
    return market_id


def _mock_day(direct_vm, body: str = DAY_BODY):
    direct_vm.mock_web(r"archive-api\.open-meteo\.com", {"status": 200, "body": body})
    direct_vm.mock_web(r"power\.larc\.nasa\.gov", {"status": 200, "body": body})


# ---------------------------------------------------------------------------
# a failed transfer leaves a recoverable obligation
# ---------------------------------------------------------------------------


def test_claiming_reserves_the_obligation_and_keeps_it_recoverable(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _market(contract, direct_vm, direct_alice, direct_bob)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    bet(contract, direct_vm, direct_charlie, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    _mock_day(direct_vm)
    mock_metric_llm(direct_vm, metric=346)
    direct_vm.sender = direct_alice
    contract.resolve_market(market_id)

    direct_vm.sender = direct_bob
    amount = int(contract.claim(market_id))
    assert amount > 0

    accounting = contract.get_accounting()
    # The money is reserved, not paid out.
    assert accounting["owed_all"] == amount
    assert accounting["paid_out_all"] == 0
    assert accounting["in_flight_all"] == amount

    pending = contract.get_pending_payouts()
    assert pending["count"] == 1
    assert pending["pending"][0]["owed"] == amount
    assert pending["pending"][0]["delivered"] is False


def test_claiming_again_retries_without_paying_twice(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """A retry is only allowed once a failure came after the last attempt."""
    contract = deploy(direct_deploy)
    market_id = _market(contract, direct_vm, direct_alice, direct_bob)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    _mock_day(direct_vm)
    mock_metric_llm(direct_vm, metric=346)
    direct_vm.sender = direct_alice
    contract.resolve_market(market_id)

    direct_vm.sender = direct_bob
    first = int(contract.claim(market_id))

    # The money is in flight, so a second transfer would send it twice.
    with direct_vm.expect_revert("already in flight"):
        contract.claim(market_id)

    # The transfer failed and the value came back, so the retry is allowed.
    direct_vm.value = first
    contract.__on_errored_message__()
    direct_vm.value = 0

    second = int(contract.claim(market_id))
    assert first == second

    accounting = contract.get_accounting()
    # One attempt is in flight, not two.
    assert accounting["in_flight_all"] == first
    assert accounting["owed_all"] == first
    assert accounting["paid_out_all"] == 0


def test_confirming_the_delivery_moves_the_obligation_to_paid(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = deploy(direct_deploy)
    market_id = _market(contract, direct_vm, direct_alice, direct_bob)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    _mock_day(direct_vm)
    mock_metric_llm(direct_vm, metric=346)
    direct_vm.sender = direct_alice
    contract.resolve_market(market_id)

    direct_vm.sender = direct_bob
    amount = int(contract.claim(market_id))
    contract.confirm_payout(market_id, 0)

    accounting = contract.get_accounting()
    assert accounting["owed_all"] == 0
    assert accounting["paid_out_all"] == amount
    assert accounting["in_flight_all"] == 0
    assert contract.get_pending_payouts()["count"] == 0


def test_a_delivery_cannot_be_confirmed_twice(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = deploy(direct_deploy)
    market_id = _market(contract, direct_vm, direct_alice, direct_bob)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    _mock_day(direct_vm)
    mock_metric_llm(direct_vm, metric=346)
    direct_vm.sender = direct_alice
    contract.resolve_market(market_id)

    direct_vm.sender = direct_bob
    contract.claim(market_id)
    contract.confirm_payout(market_id, 0)

    with direct_vm.expect_revert("already confirmed"):
        contract.confirm_payout(market_id, 0)


def test_a_claimed_position_cannot_be_claimed_again_after_confirmation(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = deploy(direct_deploy)
    market_id = _market(contract, direct_vm, direct_alice, direct_bob)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    _mock_day(direct_vm)
    mock_metric_llm(direct_vm, metric=346)
    direct_vm.sender = direct_alice
    contract.resolve_market(market_id)

    direct_vm.sender = direct_bob
    contract.claim(market_id)
    contract.confirm_payout(market_id, 0)

    with direct_vm.expect_revert("already paid out"):
        contract.claim(market_id)


def test_a_failed_transfer_returns_the_value_and_keeps_the_obligation(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """The child transfer failed: the value comes back and the claim can be retried."""
    contract = deploy(direct_deploy)
    market_id = _market(contract, direct_vm, direct_alice, direct_bob)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    _mock_day(direct_vm)
    mock_metric_llm(direct_vm, metric=346)
    direct_vm.sender = direct_alice
    contract.resolve_market(market_id)

    direct_vm.sender = direct_bob
    amount = int(contract.claim(market_id))
    assert contract.get_accounting()["in_flight_all"] == amount

    # The transfer fails and the value comes back.
    direct_vm.value = amount
    contract.__on_errored_message__()
    direct_vm.value = 0

    accounting = contract.get_accounting()
    assert accounting["in_flight_all"] == 0
    assert accounting["failed_transfers"] == 1
    # The obligation is untouched, so the money is still owed.
    assert accounting["owed_all"] == amount
    assert contract.get_pending_payouts()["count"] == 1

    # And the bettor can have it delivered, exactly once.
    direct_vm.sender = direct_bob
    assert int(contract.claim(market_id)) == amount
    contract.confirm_payout(market_id, 0)
    assert contract.get_accounting()["paid_out_all"] == amount
    assert contract.get_pending_payouts()["count"] == 0


# ---------------------------------------------------------------------------
# nobody backed the winner
# ---------------------------------------------------------------------------


def test_stranded_value_can_be_swept(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_owner
):
    """A rejected transaction can leave money that no market accounts for."""
    contract = deploy(direct_deploy)
    market_id = _market(contract, direct_vm, direct_alice, direct_bob)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    _mock_day(direct_vm)
    mock_metric_llm(direct_vm, metric=346)
    direct_vm.sender = direct_alice
    contract.resolve_market(market_id)

    # Something lands in the contract that no market accounts for.
    from conftest import fund_contract

    fund_contract(direct_vm, 250 * GEN)

    accounting = contract.get_accounting()
    assert accounting["stranded"] == 150 * GEN
    assert accounting["covered"] is True

    # The grace period has to pass before the owner may sweep.
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("grace period has not elapsed"):
        contract.sweep_stranded()

    warp_to(direct_vm, now_ts() + 30 * 86400 + 120)
    before = contract.get_accounting()
    swept = int(contract.sweep_stranded())
    assert swept == before["stranded"]
    assert swept == 150 * GEN

    accounting = contract.get_accounting()
    assert accounting["stranded"] == 0
    # The protocol now owns the one GEN fee plus the swept hundred and fifty.
    assert accounting["fees_collected"] == 151 * GEN
    assert accounting["swept_stranded"] == 150 * GEN


def test_a_market_nobody_backed_is_voided(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _market(contract, direct_vm, direct_alice, direct_bob)
    # Only "No" is backed. If the market resolves to "Yes", nobody won.
    bet(contract, direct_vm, direct_bob, market_id, 1, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    _mock_day(direct_vm)
    # The threshold is met, so the outcome is "Yes" while nobody backed it.
    mock_metric_llm(direct_vm, metric=346)
    direct_vm.sender = direct_alice
    contract.resolve_market(market_id)

    market = contract.get_market(market_id)
    assert market["status"] == "voided"

    # The losing side gets its stake back instead of losing it.
    direct_vm.sender = direct_bob
    assert int(contract.claim_refund(market_id)) == 100 * GEN


# ---------------------------------------------------------------------------
# the resolution has to be about the right day
# ---------------------------------------------------------------------------


def test_a_source_that_does_not_cover_the_target_day_does_not_settle(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = deploy(direct_deploy)
    market_id = _market(contract, direct_vm, direct_alice, direct_bob)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    # The page is about another day entirely.
    _mock_day(direct_vm, body="2026-11-02 daily maximum temperature 34.6 degrees Celsius.")
    mock_metric_llm(direct_vm, metric=346)
    direct_vm.sender = direct_alice
    contract.resolve_market(market_id)

    market = contract.get_market(market_id)
    assert market["status"] == "voided"
    resolution = json.loads(market["resolution"])
    assert "day" in resolution["consensus"]["undetermined_reason"]


def test_a_source_that_covers_the_target_day_settles(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = deploy(direct_deploy)
    market_id = _market(contract, direct_vm, direct_alice, direct_bob)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    _mock_day(direct_vm)
    mock_metric_llm(direct_vm, metric=346)
    direct_vm.sender = direct_alice
    contract.resolve_market(market_id)

    market = contract.get_market(market_id)
    assert market["status"] == "resolved"
    assert market["outcome"] == 0
    assert market["metric_value"] == 346


# ---------------------------------------------------------------------------
# the dispute is kept with the market
# ---------------------------------------------------------------------------


def test_the_dispute_is_kept_with_the_market(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _market(contract, direct_vm, direct_alice, direct_bob)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    _mock_day(direct_vm)
    mock_metric_llm(direct_vm, metric=346)
    direct_vm.sender = direct_alice
    contract.resolve_market(market_id)

    direct_vm.mock_web(
        r"open-meteo\.com/correction",
        {"status": 200, "body": "Correction: the reading was wrong."},
    )
    direct_vm.mock_llm(
        r"Decide whether the CHALLENGE EVIDENCE",
        json.dumps(
            {
                "challenge_valid": True,
                "reasoning": "The correction shows the recorded outcome is wrong.",
                "citations": [
                    {
                        "source_index": 1,
                        "quote": "Correction: the reading was wrong.",
                    }
                ],
            }
        ),
    )

    direct_vm.sender = direct_charlie
    direct_vm.value = 10**17
    valid = contract.challenge_market(
        market_id, "https://open-meteo.com/correction"
    )
    direct_vm.value = 0

    assert valid is True
    market = contract.get_market(market_id)
    assert market["status"] == "voided"
    assert market["challenge_url"] == "https://open-meteo.com/correction"
    assert market["challenge_verdict"] is True
    assert "recorded outcome" in market["challenge_reasoning"]

    trail = contract.get_citations(market_id)
    assert len(trail["challenge"]["citations"]) == 1
    assert "Correction" in trail["challenge"]["citations"][0]["quote"]


def test_a_dispute_from_an_untrusted_publisher_is_refused(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _market(contract, direct_vm, direct_alice, direct_bob)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)

    _mock_day(direct_vm)
    mock_metric_llm(direct_vm, metric=346)
    direct_vm.sender = direct_alice
    contract.resolve_market(market_id)

    direct_vm.sender = direct_charlie
    direct_vm.value = 10**17
    with direct_vm.expect_revert("trusted publisher"):
        contract.challenge_market(market_id, "https://random-blog.example/correction")
    direct_vm.value = 0
