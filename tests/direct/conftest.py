"""Shared helpers for the direct mode tests."""

import datetime as _datetime_module
import json
from pathlib import Path

CONTRACT_PATH = str(Path(__file__).resolve().parents[2] / "contracts" / "cite.py")

GEN = 10**18
HOUR = 60 * 60
DAY = 24 * HOUR

QUESTION = "Will ETH close above 5000 USD on 2026-12-31?"
CRITERIA = "Resolve using the daily ETH/USD closing price published on the sources."

SOURCE_A = "https://news.example.com/eth-outlook"
SOURCE_B = "https://data.example.org/eth-prices"

# A sentence that is present, verbatim, in the mocked page bodies.
QUOTE = "ETH closed at 5120 USD on 2026-12-31."

# The same, for the weather markets.
WEATHER_QUOTE = "The daily maximum temperature in Jakarta was 33.4 degrees Celsius."

RESOLUTION_PROMPT = r"Decide which outcome of the market is true|Answer the market question"
CHALLENGE_PROMPT = r"Decide whether the CHALLENGE EVIDENCE"


def now_ts() -> int:
    """The (possibly warped) transaction time.

    ``datetime.datetime`` is looked up on the module at call time on purpose:
    the direct mode runner patches it so that ``now()`` follows
    ``direct_vm.warp()``.
    """
    return int(
        _datetime_module.datetime.now(_datetime_module.timezone.utc).timestamp()
    )


def addr_hex(value) -> str:
    """Checksummed hex of an address, whichever representation it uses."""
    if hasattr(value, "as_hex"):
        return value.as_hex
    if isinstance(value, (bytes, bytearray)):
        from genlayer.py.types import Address

        return Address(bytes(value)).as_hex
    return str(value)


def warp_to(direct_vm, ts: int) -> None:
    """Move the VM clock to a unix timestamp."""
    direct_vm.warp(
        _datetime_module.datetime.fromtimestamp(
            ts, _datetime_module.timezone.utc
        ).isoformat()
    )


def deploy(direct_deploy):
    return direct_deploy(CONTRACT_PATH)


def create_market(
    contract,
    *,
    question: str = QUESTION,
    criteria: str = CRITERIA,
    outcomes=("Yes", "No"),
    sources=(SOURCE_A, SOURCE_B),
    allowed_domains=(),
    close_in: int = HOUR,
    resolution_in: int = DAY,
    challenge_window: int = HOUR,
    resolution_mode: str = "choice",
    comparator: str = ">=",
    threshold: int = 0,
    metric_name: str = "",
    window_start_ts: int = 0,
    window_end_ts: int = 0,
    require_citation: bool = False,
    measurement: dict = None,
    event_urls=(),
    event_domains=(),
):
    """Create a market with sensible defaults for the tests."""
    now = now_ts()
    return contract.create_market(
        question=question,
        criteria=criteria,
        outcomes=list(outcomes),
        source_urls=list(sources),
        allowed_domains=list(allowed_domains),
        close_ts=now + close_in,
        resolution_deadline_ts=now + resolution_in,
        challenge_window=challenge_window,
        resolution_mode=resolution_mode,
        comparator=comparator,
        threshold=threshold,
        metric_name=metric_name,
        window_start_ts=window_start_ts,
        window_end_ts=window_end_ts,
        require_citation=require_citation,
        measurement_json=json.dumps(measurement) if measurement else "",
        event_urls=list(event_urls),
        event_domains=list(event_domains),
    )


def bet(contract, direct_vm, bettor, market_id, outcome: int, amount: int) -> None:
    """Place a bet and reset the message value afterwards."""
    direct_vm.sender = bettor
    direct_vm.value = amount
    try:
        contract.place_bet(market_id, outcome)
    finally:
        direct_vm.value = 0


def mock_sources(direct_vm, body: str = QUOTE) -> None:
    """Mock both allowlisted sources with a body that mentions the subject."""
    direct_vm.mock_web(r"news\.example\.com/eth-outlook", {"status": 200, "body": body})
    direct_vm.mock_web(r"data\.example\.org/eth-prices", {"status": 200, "body": body})


def mock_resolution_llm(
    direct_vm,
    outcome_index: int = 0,
    confidence: int = 88,
    quote: str = QUOTE,
    source_index: int = 1,
    uncited: bool = False,
) -> None:
    direct_vm.mock_llm(
        RESOLUTION_PROMPT,
        json.dumps(
            {
                "resolved": True,
                "outcome_index": outcome_index,
                "confidence": confidence,
                "reasoning": "Both sources report the event occurred.",
                "citations": (
                    []
                    if uncited
                    else [{"source_index": source_index, "quote": quote}]
                ),
                "uncited": uncited,
            }
        ),
    )


def mock_metric_llm(
    direct_vm,
    metric: int,
    confidence: int = 88,
    quote: str = QUOTE,
    source_index: int = 1,
    uncited: bool = False,
) -> None:
    direct_vm.mock_llm(
        RESOLUTION_PROMPT,
        json.dumps(
            {
                "metric": metric,
                "confidence": confidence,
                "reasoning": "Counted every qualifying occurrence.",
                "citations": (
                    []
                    if uncited
                    else [{"source_index": source_index, "quote": quote}]
                ),
                "uncited": uncited,
            }
        ),
    )


def mock_challenge_llm(direct_vm, valid: bool) -> None:
    direct_vm.mock_llm(
        CHALLENGE_PROMPT,
        json.dumps(
            {
                "challenge_valid": valid,
                "reasoning": "The challenge evidence was considered.",
            }
        ),
    )


def fund_contract(direct_vm, amount: int) -> None:
    """Give the contract a balance so the accounting invariant can be checked."""
    direct_vm.deal(direct_vm._contract_address, amount)
