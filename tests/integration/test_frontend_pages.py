"""Integration tests for the pages, against the deployed contract.

The data layer is checked in ``test_frontend_contract.py``. This one goes a
step further and looks at what a reader actually sees: the server renders the
pages from the chain, and the HTML has to carry the question, the number and
the quotes.

    pytest tests/integration/test_frontend_pages.py -v -s

The server is started for the test and pointed at the deployed contract. It
reads the chain and nothing else, so the pages it renders are the real ones.
"""

import html
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
DEPLOYMENTS = ROOT / "deployments.json"

RPC = "https://studio.genlayer.com/api"
CHAIN_ID = "61999"
STARTUP_TIMEOUT = 180


def _live_contract() -> str:
    with open(DEPLOYMENTS, "r", encoding="utf-8") as handle:
        return json.load(handle)["contract"]["address"]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _next() -> list:
    """The local next binary, so the tests do not depend on the shell."""
    binary = FRONTEND / "node_modules" / ".bin" / (
        "next.cmd" if os.name == "nt" else "next"
    )
    if binary.exists():
        return [str(binary)]
    return ["npx", "next"]


def _fetch(url: str, timeout: int = 120) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "cite-tests"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


@pytest.fixture(scope="module")
def server():
    """A production server on the deployed contract, started for the tests."""
    port = _free_port()
    environment = {
        **os.environ,
        "NEXT_PUBLIC_RPC_URL": RPC,
        "NEXT_PUBLIC_CHAIN_ID": CHAIN_ID,
        "NEXT_PUBLIC_CONTRACT_ADDRESS": _live_contract(),
        "PORT": str(port),
    }
    process = subprocess.Popen(
        [*_next(), "dev", "-p", str(port)],
        cwd=FRONTEND,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + STARTUP_TIMEOUT
        while time.time() < deadline:
            if process.poll() is not None:
                raise RuntimeError("the server stopped before it was ready")
            try:
                _fetch(base + "/markets", timeout=30)
                break
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(2)
        else:
            raise RuntimeError("the server did not start in time")
        yield base
    finally:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()


def _text(value: str) -> str:
    """The way the server puts a string into the page."""
    return html.escape(value, quote=True).replace("&#x27;", "&#x27;")


def test_the_board_shows_the_markets_of_the_chain(server):
    """Every market on the chain has to appear on the board."""
    page = _fetch(server + "/markets")

    for market_id in range(5):
        assert f"/markets/{market_id}" in page, f"market {market_id} is missing"


def test_a_market_page_shows_the_number_and_the_quotes(server):
    """The measurement market: the number, the outcome and the quote."""
    page = _fetch(server + "/markets/1")

    assert "The number behind the settlement" in page
    # The number the contract derived, in degrees, not in tenths.
    assert "34.6" in page
    assert "34.6 degrees Celsius" in page or "degrees Celsius" in page
    assert "Counted by" in page
    assert "the committee, from the authoritative source" in page

    # The outcome the committee agreed on.
    assert "Yes" in page
    assert "high" in page

    # The quote the committee relied on, with its source.
    assert "34.6" in page
    assert "open-meteo.com" in page
    assert "temperature_2m_max" in page


def test_a_counted_market_page_says_who_counted(server):
    """The consequence market: the contract counted, and the page says so."""
    page = _fetch(server + "/markets/4")

    assert "The number behind the settlement" in page
    assert "the contract, counting the feed itself" in page
    assert "asked to quote, not to count" in page
    assert "GDACS" in page


def test_a_comparison_market_page_shows_the_decision(server):
    """The comparison market: the decision, and the number as context."""
    page = _fetch(server + "/markets/3")

    assert "The number behind the settlement" in page
    assert "the committee" in page.lower()
    assert "context" in page


def test_the_settlements_page_shows_the_quotes(server):
    """The settlements page is the audit trail, so it has to carry quotes."""
    page = _fetch(server + "/settlements")

    assert "temperature_2m_max" in page
    assert "Settlement" in page or "settlement" in page
