"""Market creation, betting and odds."""

import pytest

from conftest import (
    GEN,
    HOUR,
    addr_hex,
    bet,
    create_market,
    deploy,
    now_ts,
    warp_to,
)


def test_create_market_registers_the_market(direct_vm, direct_deploy, direct_alice):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice

    market_id = create_market(contract)

    assert int(market_id) == 0
    assert int(contract.get_market_count()) == 1

    market = contract.get_market(market_id)
    assert market["status"] == "open"
    assert market["outcomes"] == ["Yes", "No"]
    assert market["total_staked"] == 0
    assert market["pools"] == [0, 0]
    assert market["creator"] == addr_hex(direct_alice)
    # The allowed domains are derived from the source urls.
    assert market["allowed_domains"] == ["example.com", "example.org"]


def test_create_market_rejects_a_short_question(direct_vm, direct_deploy, direct_alice):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("the question is too short"):
        create_market(contract, question="ETH?")


def test_create_market_rejects_a_single_outcome(direct_vm, direct_deploy, direct_alice):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("at least 2 outcomes"):
        create_market(contract, outcomes=("Yes",))


def test_create_market_rejects_duplicate_outcomes(direct_vm, direct_deploy, direct_alice):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("duplicate outcome label"):
        create_market(contract, outcomes=("Yes", "yes"))


def test_create_market_rejects_a_non_http_source(direct_vm, direct_deploy, direct_alice):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("must be http"):
        create_market(contract, sources=("ftp://news.example.com/eth",))


def test_create_market_rejects_a_close_date_in_the_past(direct_vm, direct_deploy, direct_alice):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("close_ts must be in the future"):
        create_market(contract, close_in=-10)


def test_create_market_rejects_a_deadline_before_the_close(direct_vm, direct_deploy, direct_alice):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("must be after close_ts"):
        create_market(contract, close_in=HOUR, resolution_in=60)


def test_place_bet_moves_the_money_into_the_pool(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(contract)

    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)

    market = contract.get_market(market_id)
    assert market["pools"] == [100 * GEN, 0]
    assert market["total_staked"] == 100 * GEN

    position = contract.get_position(market_id, direct_bob, 0)
    assert position["stake"] == 100 * GEN
    assert position["paid"] == 0
    assert position["bettor"] == addr_hex(direct_bob)


def test_place_bet_accumulates_on_the_same_position(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(contract)

    bet(contract, direct_vm, direct_bob, market_id, 0, 100 * GEN)
    bet(contract, direct_vm, direct_bob, market_id, 0, 50 * GEN)

    market = contract.get_market(market_id)
    assert market["pools"] == [150 * GEN, 0]
    assert market["total_staked"] == 150 * GEN
    assert contract.get_position(market_id, direct_bob, 0)["stake"] == 150 * GEN


def test_place_bet_rejects_an_unknown_outcome(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(contract)

    with direct_vm.expect_revert("unknown outcome index"):
        bet(contract, direct_vm, direct_bob, market_id, 7, 10 * GEN)


def test_place_bet_rejects_a_bet_below_the_minimum(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(contract)

    with direct_vm.expect_revert("below the minimum size"):
        bet(contract, direct_vm, direct_bob, market_id, 0, 1)


def test_place_bet_is_rejected_after_the_close(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(contract, close_in=HOUR)

    warp_to(direct_vm, now_ts() + HOUR + 60)

    with direct_vm.expect_revert("betting is closed"):
        bet(contract, direct_vm, direct_bob, market_id, 0, 10 * GEN)


def test_close_market_moves_the_status(direct_vm, direct_deploy, direct_alice):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(contract, close_in=HOUR)

    with direct_vm.expect_revert("betting is still open"):
        contract.close_market(market_id)

    warp_to(direct_vm, now_ts() + HOUR + 60)
    contract.close_market(market_id)
    assert contract.get_market(market_id)["status"] == "closed"


def test_odds_are_derived_from_the_pools(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    market_id = create_market(contract)

    bet(contract, direct_vm, direct_bob, market_id, 0, 250 * GEN)
    bet(contract, direct_vm, direct_charlie, market_id, 1, 750 * GEN)

    odds = contract.get_market_odds(market_id)
    assert odds["total_staked"] == 1000 * GEN
    assert odds["implied_probability_bps"] == [2500, 7500]
    # 1000/250 -> 4.0x, expressed in basis points.
    assert odds["odds_bps"] == [40000, 13333]


def test_markets_are_enumerated(direct_vm, direct_deploy, direct_alice):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice

    first = create_market(contract)
    second = create_market(contract)

    listing = contract.get_markets(0, 10)
    assert listing["total"] == 2
    assert listing["market_ids"] == [int(first), int(second)]
