"""Integration tests between the contract and the frontend.

The frontend never talks to the chain directly. It goes through
``frontend/src/lib/cite.ts``, which is where the field names, the number
conversions and the JSON parsing live. A contract change that renames a
field, or a return value that arrives as a string instead of a number, breaks
the interface long before it breaks the contract.

These tests read the deployed contract twice. Once through the chain client,
which returns the contract's own view, and once through the frontend's read
layer, through ``frontend/scripts/contract-read.ts``. The two views have to
agree on every field the interface shows.

    pytest tests/integration/test_frontend_contract.py -v -s

The write path, a market created on chain and then read by the interface, is
in ``test_frontend_write_path.py`` because it needs a deployment of its own.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from genlayer_py import create_client, studionet

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from wallet import load_account  # noqa: E402

FRONTEND = ROOT / "frontend"
DEPLOYMENTS = ROOT / "deployments.json"
RPC = "https://studio.genlayer.com/api"
CHAIN_ID = 61999

# The fields the interface depends on. If the contract renames one of them,
# the frontend would quietly show a blank, and this is what catches it.
MARKET_FIELDS = (
    "market_id",
    "creator",
    "question",
    "criteria",
    "outcomes",
    "source_urls",
    "allowed_domains",
    "close_ts",
    "resolution_deadline_ts",
    "challenge_deadline_ts",
    "status",
    "outcome",
    "confidence",
    "resolved_at",
    "pools",
    "total_staked",
    "paid_out",
    "refunded",
    "fee_wei",
    "challenge_count",
    "swept",
    "resolution_mode",
    "comparator",
    "threshold",
    "metric_name",
    "metric_value",
    "window_start_ts",
    "window_end_ts",
    "require_citation",
    "citations_verified",
    "cited_domains",
    "measurement",
    "event_urls",
    "event_domains",
    "event_citations_verified",
)


def _live_contract() -> str:
    """The contract the frontend points at, taken from the deployment record."""
    with open(DEPLOYMENTS, "r", encoding="utf-8") as handle:
        record = json.load(handle)
    return record["contract"]["address"]


@pytest.fixture(scope="module")
def client():
    """A chain client with a wallet, so the tests can read and write."""
    return create_client(studionet, account=load_account("tester1"))


@pytest.fixture(scope="module")
def contract_address() -> str:
    return _live_contract()


def _tsx() -> list:
    """The local tsx binary, so the tests never reach for the network."""
    binary = FRONTEND / "node_modules" / ".bin" / (
        "tsx.cmd" if os.name == "nt" else "tsx"
    )
    if binary.exists():
        return [str(binary)]
    return ["npx", "tsx"]


def _bridge(command: str, *arguments, contract_address: str):
    """Read the chain through the frontend's own read layer."""
    # The network allows thirty requests a minute. The reads are spread out so
    # a full run never trips the limit.
    time.sleep(2)
    environment = {
        **os.environ,
        "NEXT_PUBLIC_RPC_URL": RPC,
        "NEXT_PUBLIC_CHAIN_ID": str(CHAIN_ID),
        "NEXT_PUBLIC_CONTRACT_ADDRESS": contract_address,
    }
    completed = subprocess.run(
        [
            *_tsx(),
            "scripts/contract-read.ts",
            command,
            *[str(argument) for argument in arguments],
        ],
        cwd=FRONTEND,
        env=environment,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, (
        f"the frontend could not read '{command}':\n{completed.stderr}"
    )
    return json.loads(completed.stdout)


def test_the_frontend_reads_every_market_the_way_the_chain_stores_it(
    client, contract_address
):
    """Every field the interface shows has to be the field the chain holds."""
    count = int(client.read_contract(contract_address, "get_market_count"))
    assert count > 0

    for market_id in range(count):
        stored = client.read_contract(
            contract_address, "get_market", args=[market_id]
        )
        shown = _bridge("market", market_id, contract_address=contract_address)

        for field in MARKET_FIELDS:
            assert field in shown, f"market {market_id}: the interface lost '{field}'"
            assert shown[field] == stored[field], (
                f"market {market_id}: the interface changed '{field}'"
            )

        # The interface adds nothing the chain does not have.
        assert set(shown) - set(stored) == set()
        assert shown["market_id"] == market_id
        assert shown["question"].strip()
        assert shown["status"] in ("open", "closed", "resolved", "settled", "voided")


def test_the_frontend_shows_the_odds_the_contract_computes(client, contract_address):
    """The odds panel is fed by the contract, and has to agree with it."""
    count = int(client.read_contract(contract_address, "get_market_count"))

    for market_id in range(count):
        stored = client.read_contract(
            contract_address, "get_market_odds", args=[market_id]
        )
        shown = _bridge("odds", market_id, contract_address=contract_address)

        for field in ("market_id", "status", "outcomes", "pools", "total_staked"):
            assert shown[field] == stored[field], (
                f"market {market_id}: the interface changed '{field}'"
            )

        # The probability is the interface's own arithmetic on the pools.
        total = shown["total_staked"]
        assert sum(shown["pools"]) == total
        if total > 0:
            assert shown["implied_probability_bps"][0] + (
                shown["implied_probability_bps"][1]
            ) == 10000


def test_the_frontend_shows_the_citation_trail(client, contract_address):
    """The trail is the whole point of the product, so it has to survive."""
    count = int(client.read_contract(contract_address, "get_market_count"))
    checked = 0

    for market_id in range(count):
        stored = client.read_contract(
            contract_address, "get_citations", args=[market_id]
        )
        shown = _bridge("citations", market_id, contract_address=contract_address)

        assert shown["market_id"] == stored["market_id"]
        assert shown["status"] == stored["status"]
        assert shown["citations_verified"] == stored["citations_verified"]
        assert shown["cited_domains"] == stored["cited_domains"]
        assert len(shown["trail"]) == len(stored["trail"])

        for entry, expected in zip(shown["trail"], stored["trail"]):
            assert entry["quote"] == expected["quote"]
            assert entry["url"] == expected["url"]
            assert entry["source_index"] == expected["source_index"]
            assert entry["quote"].strip()
            if entry["url"]:
                assert entry["url"].startswith("http")

        assert shown["challenge"]["url"] == stored["challenge"]["url"]
        assert shown["challenge"]["verdict"] == stored["challenge"]["verdict"]
        checked += 1

    assert checked == count


def test_the_frontend_shows_the_accounting_the_contract_keeps(
    client, contract_address
):
    """The accounting page is the auditor's view, so it has to be exact."""
    stored = client.read_contract(contract_address, "get_accounting")
    shown = _bridge("accounting", contract_address=contract_address)

    for field, value in stored.items():
        assert shown[field] == value, f"the interface changed '{field}'"

    assert shown["covered"] is True
    assert shown["reconciled"] is True
    assert shown["invariant_holds"] is True
    assert shown["market_count"] >= 1


def test_the_frontend_reads_the_market_count(client, contract_address):
    stored = client.read_contract(contract_address, "get_market_count")
    shown = _bridge("count", contract_address=contract_address)
    assert shown == int(stored)
    assert shown >= 1


def test_the_frontend_reads_the_pending_payouts(client, contract_address):
    """The payout queue is what a bettor checks after a settlement.

    The contract returns a struct with the count and the list, and the
    interface shows the list itself, so the two are compared on the list.
    """
    stored = client.read_contract(contract_address, "get_pending_payouts")
    assert stored["count"] == len(stored["pending"])

    shown = _bridge("pending", contract_address=contract_address)
    assert len(shown) == len(stored["pending"])

    for entry, expected in zip(shown, stored["pending"]):
        assert entry["market_id"] == expected["market_id"]
        assert entry["bettor"] == expected["bettor"]
        assert entry["outcome"] == expected["outcome"]
        assert entry["owed"] == expected["owed"]
        assert entry["delivered"] == expected["delivered"]
