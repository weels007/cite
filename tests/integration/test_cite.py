"""Integration tests: Cite running on a real GenLayer network.

These tests exercise the full consensus path (leader + validators, real web
requests and real LLM calls). They are much slower than the direct mode tests
and they need a network:

    pytest tests/integration/test_cite.py -v -s

The chain client is used directly rather than through the typed test
framework, because the typed one has to fetch the contract schema by source
code, and the contract's source is not plain ASCII.

The markets live on a deployment of their own, so the deployed contract of the
project is never touched.
"""

import json
import sys
import time
from pathlib import Path

import pytest
from genlayer_py import create_client, studionet

ROOT = Path(__file__).resolve().parents[2]
# The network allows thirty requests a minute, and a receipt poll is a request.
# A ten second poll keeps a whole run inside that budget.
POLL_INTERVAL = 10_000

sys.path.insert(0, str(ROOT / "scripts"))
from wallet import load_account  # noqa: E402

CONTRACT_PATH = ROOT / "contracts" / "cite.py"

SOURCE_A = "https://en.wikipedia.org/wiki/Ethereum"
SOURCE_B = "https://en.wikipedia.org/wiki/Bitcoin"

QUESTION = "Will the Wikipedia article about Ethereum exist before 1 January 2030?"
CRITERIA = (
    "Resolve Yes when the Wikipedia article about Ethereum exists and is not a "
    "redirect, No otherwise."
)

METRIC_QUESTION = (
    "According to the source, in which year was the Ethereum project launched?"
)
METRIC_CRITERIA = (
    "Take the year the project was launched from the source, and resolve Yes "
    "when that year is 2015 or later."
)


def _accepted(receipt) -> bool:
    """The transaction made it through consensus, it was not rejected."""
    return receipt["status_name"] in ("ACCEPTED", "FINALIZED")


@pytest.fixture(scope="module")
def account():
    return load_account("tester1")


@pytest.fixture(scope="module")
def client(account):
    return create_client(studionet, account=account)


@pytest.fixture(scope="module")
def contract(client, account):
    """A deployment of its own, so the project contract is never touched."""
    code = CONTRACT_PATH.read_text(encoding="utf-8")
    transaction_hash = client.deploy_contract(code=code, account=account)
    receipt = client.wait_for_transaction_receipt(
        transaction_hash, retries=60, interval=POLL_INTERVAL
    )
    address = receipt["data"]["contract_address"]
    assert address, f"the deployment produced no address: {receipt}"
    return address


def _wait_for_close(close_ts: int) -> None:
    """Sleep until the betting window of the market is closed."""
    delay = close_ts - int(time.time())
    if delay > 0:
        time.sleep(delay + 2)


def _create(client, account, contract: str, question, criteria, **overrides) -> int:
    """Create a market and return its close time."""
    now = int(time.time())
    kwargs = {
        "question": question,
        "criteria": criteria,
        "outcomes": ["Yes", "No"],
        "source_urls": [SOURCE_A, SOURCE_B],
        "allowed_domains": [],
        "close_ts": now + 30,
        "resolution_deadline_ts": now + 3600,
        "challenge_window": 600,
        "resolution_mode": "choice",
        "comparator": ">=",
        "threshold": 0,
        "metric_name": "",
        "window_start_ts": 0,
        "window_end_ts": 0,
        "require_citation": False,
        "measurement_json": json.dumps({}),
        "event_urls": [],
        "event_domains": [],
    }
    kwargs.update(overrides)
    transaction_hash = client.write_contract(
        contract, "create_market", account=account, kwargs=kwargs
    )
    receipt = client.wait_for_transaction_receipt(
        transaction_hash, retries=60, interval=POLL_INTERVAL
    )
    assert _accepted(receipt), receipt
    return kwargs["close_ts"]


def _bet(client, account, contract: str, market_id: int, outcome: int, value: int):
    transaction_hash = client.write_contract(
        contract,
        "place_bet",
        account=account,
        args=[market_id, outcome],
        value=value,
    )
    receipt = client.wait_for_transaction_receipt(
        transaction_hash, retries=60, interval=POLL_INTERVAL
    )
    assert _accepted(receipt), receipt


def _resolve(client, account, contract: str, market_id: int, attempts: int = 3):
    """Resolve a market.

    The committee runs on a hosted model, and a model that is momentarily
    unavailable fails the execution. A failed resolution leaves the market
    open, so the resolution is simply tried again.
    """
    last = None
    for attempt in range(attempts):
        try:
            transaction_hash = client.write_contract(
                contract, "resolve_market", account=account, args=[market_id]
            )
            receipt = client.wait_for_transaction_receipt(
                transaction_hash, retries=60, interval=POLL_INTERVAL
            )
        except Exception as error:  # noqa: BLE001 - the message decides
            last = error
        else:
            if _accepted(receipt):
                return receipt
            last = AssertionError(receipt)
        if attempt < attempts - 1:
            print(f"\n  the resolution did not go through, trying again")
            time.sleep(20)
    raise last


def test_full_market_lifecycle(client, account, contract):
    _create(client, account, contract, QUESTION, CRITERIA)

    market = client.read_contract(contract, "get_market", args=[0])
    assert market["status"] == "open"
    assert market["outcomes"] == ["Yes", "No"]
    assert market["resolution_mode"] == "choice"

    _bet(client, account, contract, 0, 0, 10 * 10**18)

    odds = client.read_contract(contract, "get_market_odds", args=[0])
    assert odds["total_staked"] == 10 * 10**18
    assert odds["implied_probability_bps"][0] == 10000

    _wait_for_close(int(client.read_contract(contract, "get_market", args=[0])["close_ts"]))
    _resolve(client, account, contract, 0)

    market = client.read_contract(contract, "get_market", args=[0])
    assert market["status"] in ("resolved", "voided")
    if market["status"] == "resolved":
        assert market["outcome"] in (0, 1)
        assert market["fee_wei"] == market["total_staked"] // 100


def test_a_metric_market_settles_from_the_extracted_number(client, account, contract):
    _create(
        client,
        account,
        contract,
        METRIC_QUESTION,
        METRIC_CRITERIA,
        resolution_mode="metric",
        comparator=">=",
        threshold=2015,
        metric_name="the year the project was launched",
    )

    _bet(client, account, contract, 1, 0, 5 * 10**18)

    _wait_for_close(int(client.read_contract(contract, "get_market", args=[1])["close_ts"]))
    _resolve(client, account, contract, 1)

    market = client.read_contract(contract, "get_market", args=[1])
    assert market["status"] in ("resolved", "voided")
    if market["status"] == "resolved":
        # The outcome is derived by the contract, never chosen by the model.
        assert market["outcome"] in (0, 1)
        assert market["metric_value"] >= 0


def test_the_accounting_invariant_holds(client, account, contract):
    _create(client, account, contract, QUESTION, CRITERIA)
    _bet(client, account, contract, 2, 1, 5 * 10**18)

    _wait_for_close(int(client.read_contract(contract, "get_market", args=[2])["close_ts"]))
    _resolve(client, account, contract, 2)

    accounting = client.read_contract(contract, "get_accounting")
    assert accounting["invariant_holds"] is True
    assert accounting["covered"] is True
    assert accounting["reconciled"] is True


@pytest.mark.slow
def test_a_cited_market_produces_a_verifiable_trail(client, account, contract):
    """With ``require_citation`` the settlement has to point at the source."""
    _create(
        client,
        account,
        contract,
        QUESTION,
        CRITERIA,
        require_citation=True,
    )

    _bet(client, account, contract, 3, 0, 5 * 10**18)

    _wait_for_close(int(client.read_contract(contract, "get_market", args=[3])["close_ts"]))
    _resolve(client, account, contract, 3)

    market = client.read_contract(contract, "get_market", args=[3])
    if market["status"] == "resolved":
        trail = client.read_contract(contract, "get_citations", args=[3])
        assert trail["citations_verified"] >= 1
        for entry in trail["trail"]:
            assert entry["quote"]
            assert entry["url"].startswith("http")
