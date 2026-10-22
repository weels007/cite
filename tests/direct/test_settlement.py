"""Settlement: payouts, refunds, challenges and the accounting invariant."""

from conftest import (
    GEN,
    HOUR,
    addr_hex,
    bet,
    create_market,
    deploy,
    fund_contract,
    mock_challenge_llm,
    mock_resolution_llm,
    mock_sources,
    now_ts,
    warp_to,
)

BOND = 10**17  # 0.1 GEN


def _resolved_market(contract, direct_vm, alice, bob, charlie, dave, outcome=0):
    """A market with 1000 GEN staked: 300 on outcome 0 and 700 on outcome 1.

    Bob and Charlie back outcome 0, Dave backs outcome 1. Once outcome 0 wins
    the pool of 300 GEN distributes 990 GEN (1000 minus the 1% fee).
    """
    direct_vm.sender = alice
    market_id = create_market(contract)
    bet(contract, direct_vm, bob, market_id, 0, 100 * GEN)
    bet(contract, direct_vm, charlie, market_id, 0, 200 * GEN)
    bet(contract, direct_vm, dave, market_id, 1, 700 * GEN)
    warp_to(direct_vm, now_ts() + HOUR + 60)
    mock_sources(direct_vm)
    mock_resolution_llm(direct_vm, outcome_index=outcome)
    direct_vm.sender = alice
    contract.resolve_market(market_id)
    return market_id


def test_the_winning_pool_is_paid_out_exactly(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie, direct_accounts
):
    contract = deploy(direct_deploy)
    market_id = _resolved_market(
        contract, direct_vm, direct_alice, direct_bob, direct_charlie, direct_accounts[0]
    )
    warp_to(direct_vm, int(contract.get_market(market_id)["challenge_deadline_ts"]) + 60)

    direct_vm.sender = direct_bob
    bob_payout = int(contract.claim(market_id))
    direct_vm.sender = direct_charlie
    charlie_payout = int(contract.claim(market_id))

    # floor(100 * 990 / 300) = 330 and floor(300 * 990 / 300) - 330 = 660.
    assert bob_payout == 330 * GEN
    assert charlie_payout == 660 * GEN
    # Not a single wei is created or destroyed.
    assert bob_payout + charlie_payout == 990 * GEN

    market = contract.get_market(market_id)
    assert market["paid_out"] == 990 * GEN
    assert market["fee_wei"] == 10 * GEN


def test_the_payout_does_not_depend_on_the_claim_order(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie, direct_accounts
):
    contract = deploy(direct_deploy)
    market_id = _resolved_market(
        contract, direct_vm, direct_alice, direct_bob, direct_charlie, direct_accounts[0]
    )

    # The settlement is final once the challenge window is over, so the
    # payout obligations can be created.
    warp_to(direct_vm, int(contract.get_market(market_id)["challenge_deadline_ts"]) + 60)

    # Charlie claims first this time.
    direct_vm.sender = direct_charlie
    charlie_payout = int(contract.claim(market_id))
    direct_vm.sender = direct_bob
    bob_payout = int(contract.claim(market_id))

    assert charlie_payout == 660 * GEN
    assert bob_payout == 330 * GEN
    assert bob_payout + charlie_payout == 990 * GEN


def test_a_position_cannot_be_claimed_twice(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie, direct_accounts
):
    contract = deploy(direct_deploy)
    market_id = _resolved_market(
        contract, direct_vm, direct_alice, direct_bob, direct_charlie, direct_accounts[0]
    )

    warp_to(direct_vm, int(contract.get_market(market_id)["challenge_deadline_ts"]) + 60)

    direct_vm.sender = direct_bob
    contract.claim(market_id)

    # A second claim is refused while the first transfer is in flight.
    with direct_vm.expect_revert("already in flight"):
        contract.claim(market_id)

    contract.confirm_payout(market_id, 0)

    with direct_vm.expect_revert("already paid out"):
        contract.claim(market_id)


def test_a_losing_position_cannot_be_claimed(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie, direct_accounts
):
    contract = deploy(direct_deploy)
    dave = direct_accounts[0]
    market_id = _resolved_market(
        contract, direct_vm, direct_alice, direct_bob, direct_charlie, dave
    )

    # Dave only backed the losing outcome.
    direct_vm.sender = dave
    with direct_vm.expect_revert("no winning position"):
        contract.claim(market_id)


def test_claim_is_rejected_before_the_market_is_resolved(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(contract)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)

    with direct_vm.expect_revert("has not been resolved"):
        contract.claim(market_id)


def test_a_claim_during_the_challenge_window_is_refused(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(contract)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)

    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)
    mock_sources(direct_vm)
    mock_resolution_llm(direct_vm, outcome_index=0)
    direct_vm.sender = direct_charlie
    contract.resolve_market(market_id)

    # The settlement is not final until the challenge window is over, so no
    # payout obligation may be created before that.
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("the market is still in its challenge window"):
        contract.claim(market_id)


def test_a_voided_market_refunds_every_position(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(contract, close_in=HOUR, resolution_in=2 * HOUR)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    bet(contract, direct_vm, direct_charlie, market_id, 1, 300 * GEN)

    # The deadline passes without anybody resolving the market.
    warp_to(direct_vm, now_ts() + 3 * HOUR)
    contract.void_market(market_id)

    assert contract.get_market(market_id)["status"] == "voided"

    direct_vm.sender = direct_bob
    bob_refund = int(contract.claim_refund(market_id))
    direct_vm.sender = direct_charlie
    charlie_refund = int(contract.claim_refund(market_id))

    assert bob_refund == 100 * GEN
    assert charlie_refund == 300 * GEN


def test_a_refund_cannot_be_claimed_twice(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(contract, close_in=HOUR, resolution_in=2 * HOUR)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)

    warp_to(direct_vm, now_ts() + 3 * HOUR)
    contract.void_market(market_id)

    direct_vm.sender = direct_bob
    contract.claim_refund(market_id)

    with direct_vm.expect_revert("nothing to refund"):
        contract.claim_refund(market_id)


def test_a_market_cannot_be_voided_before_the_deadline(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(contract)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)

    with direct_vm.expect_revert("can still be resolved normally"):
        contract.void_market(market_id)


def test_a_successful_challenge_voids_the_market(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie, direct_accounts
):
    contract = deploy(direct_deploy)
    market_id = _resolved_market(
        contract, direct_vm, direct_alice, direct_bob, direct_charlie, direct_accounts[0]
    )

    mock_sources(direct_vm)
    direct_vm.mock_web(
        r"news\.example\.com/correction",
        {"status": 200, "body": "Correction: the ETH close was 4100 USD, not above 5000."},
    )
    mock_challenge_llm(direct_vm, valid=True)

    direct_vm.sender = direct_charlie
    direct_vm.value = BOND
    valid = contract.challenge_market(market_id, "https://news.example.com/correction")
    direct_vm.value = 0

    assert valid is True
    market = contract.get_market(market_id)
    assert market["status"] == "voided"
    assert market["challenge_count"] == 1
    # The protocol fee is returned together with the stakes.
    assert market["fee_wei"] == 0

    # Everybody gets their stake back.
    direct_vm.sender = direct_bob
    assert int(contract.claim_refund(market_id)) == 100 * GEN
    direct_vm.sender = direct_charlie
    assert int(contract.claim_refund(market_id)) == 200 * GEN


def test_a_failed_challenge_forfeits_the_bond(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie, direct_accounts
):
    contract = deploy(direct_deploy)
    market_id = _resolved_market(
        contract, direct_vm, direct_alice, direct_bob, direct_charlie, direct_accounts[0]
    )

    mock_sources(direct_vm)
    direct_vm.mock_web(
        r"news\.example\.com/correction",
        {"status": 200, "body": "Some unrelated blog post about bananas."},
    )
    mock_challenge_llm(direct_vm, valid=False)

    direct_vm.sender = direct_charlie
    direct_vm.value = BOND
    valid = contract.challenge_market(market_id, "https://news.example.com/correction")
    direct_vm.value = 0

    assert valid is False
    market = contract.get_market(market_id)
    assert market["status"] == "resolved"
    assert market["challenge_count"] == 1

    accounting = contract.get_accounting()
    assert accounting["bonds_received_all"] == BOND
    assert accounting["bonds_returned_all"] == 0
    # The forfeited bond becomes protocol fees.
    assert accounting["fees_collected"] == market["fee_wei"] + BOND


def test_a_challenge_needs_a_bond(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie, direct_accounts
):
    contract = deploy(direct_deploy)
    market_id = _resolved_market(
        contract, direct_vm, direct_alice, direct_bob, direct_charlie, direct_accounts[0]
    )

    direct_vm.sender = direct_charlie
    direct_vm.value = 1
    with direct_vm.expect_revert("bond is too small"):
        contract.challenge_market(market_id, "https://news.example.com/correction")
    direct_vm.value = 0


def test_a_challenge_after_the_window_is_rejected(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie, direct_accounts
):
    contract = deploy(direct_deploy)
    market_id = _resolved_market(
        contract, direct_vm, direct_alice, direct_bob, direct_charlie, direct_accounts[0]
    )

    warp_to(direct_vm, now_ts() + 10 * HOUR)

    direct_vm.sender = direct_charlie
    direct_vm.value = BOND
    with direct_vm.expect_revert("challenge window has closed"):
        contract.challenge_market(market_id, "https://news.example.com/correction")
    direct_vm.value = 0


def test_only_the_owner_can_withdraw_the_fees(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie, direct_accounts
):
    contract = deploy(direct_deploy)
    market_id = _resolved_market(
        contract, direct_vm, direct_alice, direct_bob, direct_charlie, direct_accounts[0]
    )

    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("only the owner can withdraw fees"):
        contract.withdraw_fees()


def test_the_owner_withdraws_the_fees(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie, direct_accounts
):
    # Alice owns the contract, so she is the one who may withdraw the fees.
    direct_vm.sender = direct_alice
    contract = deploy(direct_deploy)
    market_id = _resolved_market(
        contract, direct_vm, direct_alice, direct_bob, direct_charlie, direct_accounts[0]
    )

    direct_vm.sender = direct_alice
    withdrawn = int(contract.withdraw_fees())
    assert withdrawn == 10 * GEN

    accounting = contract.get_accounting()
    assert accounting["fees_collected"] == 0
    assert accounting["fees_withdrawn_all"] == 10 * GEN


def test_the_accounting_invariant_holds_after_a_full_settlement(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie, direct_accounts
):
    contract = deploy(direct_deploy)
    market_id = _resolved_market(
        contract, direct_vm, direct_alice, direct_bob, direct_charlie, direct_accounts[0]
    )

    # The contract holds the stakes that were sent in.
    fund_contract(direct_vm, 1000 * GEN)

    accounting = contract.get_accounting()
    assert accounting["contract_balance"] == 1000 * GEN
    assert accounting["expected_balance"] == 1000 * GEN
    assert accounting["invariant_holds"] is True

    # The settlement is final once the challenge window is over, so the
    # payout obligations can be created.
    warp_to(direct_vm, int(contract.get_market(market_id)["challenge_deadline_ts"]) + 60)

    direct_vm.sender = direct_bob
    contract.claim(market_id)
    direct_vm.sender = direct_charlie
    contract.claim(market_id)

    # The money left the contract with the two transfers, but it is not paid
    # out until the delivery is confirmed.
    fund_contract(direct_vm, 10 * GEN)
    accounting = contract.get_accounting()
    assert accounting["paid_out_all"] == 0
    assert accounting["owed_all"] == 990 * GEN
    assert accounting["in_flight_all"] == 990 * GEN
    assert accounting["contract_balance"] == 10 * GEN
    # The contract still covers everything it owes, and the books only
    # reconcile once nothing is in flight.
    assert accounting["covered"] is True
    assert accounting["reconciled"] is False

    direct_vm.sender = direct_bob
    contract.confirm_payout(market_id, 0)
    direct_vm.sender = direct_charlie
    contract.confirm_payout(market_id, 0)

    # 990 GEN paid out, 10 GEN of fees left in the contract.
    accounting = contract.get_accounting()
    assert accounting["paid_out_all"] == 990 * GEN
    assert accounting["owed_all"] == 0
    assert accounting["in_flight_all"] == 0
    assert accounting["contract_balance"] == 10 * GEN
    assert accounting["expected_balance"] == 10 * GEN
    assert accounting["covered"] is True
    assert accounting["reconciled"] is True


def test_the_accounting_invariant_holds_after_a_void(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(contract, close_in=HOUR, resolution_in=2 * HOUR)
    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    bet(contract, direct_vm, direct_charlie, market_id, 1, 300 * GEN)
    fund_contract(direct_vm, 400 * GEN)

    warp_to(direct_vm, now_ts() + 3 * HOUR)
    contract.void_market(market_id)

    direct_vm.sender = direct_bob
    contract.claim_refund(market_id)
    direct_vm.sender = direct_charlie
    contract.claim_refund(market_id)

    fund_contract(direct_vm, 0)
    accounting = contract.get_accounting()
    assert accounting["refunded_all"] == 400 * GEN
    assert accounting["contract_balance"] == 0
    assert accounting["expected_balance"] == 0
    assert accounting["invariant_holds"] is True


def test_the_accounting_invariant_holds_after_a_successful_challenge(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie, direct_accounts
):
    contract = deploy(direct_deploy)
    market_id = _resolved_market(
        contract, direct_vm, direct_alice, direct_bob, direct_charlie, direct_accounts[0]
    )
    fund_contract(direct_vm, 1000 * GEN + BOND)

    mock_sources(direct_vm)
    direct_vm.mock_web(
        r"news\.example\.com/correction",
        {"status": 200, "body": "Correction: the ETH close was 4100 USD."},
    )
    mock_challenge_llm(direct_vm, valid=True)

    direct_vm.sender = direct_charlie
    direct_vm.value = BOND
    contract.challenge_market(market_id, "https://news.example.com/correction")
    direct_vm.value = 0

    direct_vm.sender = direct_bob
    contract.claim_refund(market_id)
    direct_vm.sender = direct_charlie
    contract.claim_refund(market_id)
    direct_vm.sender = direct_accounts[0]
    contract.claim_refund(market_id)

    # Everything left the contract: the stakes were refunded and the bond went
    # back to the challenger.
    fund_contract(direct_vm, 0)
    accounting = contract.get_accounting()
    assert accounting["bonds_received_all"] == BOND
    assert accounting["bonds_returned_all"] == BOND
    assert accounting["refunded_all"] == 1000 * GEN
    assert accounting["contract_balance"] == 0
    assert accounting["expected_balance"] == 0
    assert accounting["invariant_holds"] is True
