"""Tier 2: the contract counts the records, the model only quotes one.

The counting is deterministic, which removes the one thing an LLM is bad at.
"""

import json

from conftest import GEN, bet, create_market, deploy, now_ts, warp_to

GDACS_URL = (
    "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
    "?fromDate=2026-12-01&toDate=2026-12-31&eventType=FL"
)

# Two flood records affecting Indonesia, one that does not.
GDACS_BODY = json.dumps(
    {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "eventtype": "FL",
                    "eventid": 1104240,
                    "alertlevel": "Orange",
                    "country": "Indonesia",
                    "iso3": "IDN",
                    "fromdate": "2026-12-08T00:00:00",
                    "todate": "2026-12-12T00:00:00",
                    "description": "Orange flood alert in Indonesia",
                    "affectedcountries": [{"iso3": "IDN", "countryname": "Indonesia"}],
                    "severitydata": {"severity": 1200.0, "severityunit": "ha"},
                },
            },
            {
                "type": "Feature",
                "properties": {
                    "eventtype": "FL",
                    "eventid": 1104299,
                    "alertlevel": "Red",
                    "country": "Indonesia",
                    "iso3": "IDN",
                    "fromdate": "2026-12-20T00:00:00",
                    "todate": "2026-12-24T00:00:00",
                    "description": "Red flood alert in Indonesia",
                    "affectedcountries": [{"iso3": "IDN", "countryname": "Indonesia"}],
                    "severitydata": {"severity": 4300.0, "severityunit": "ha"},
                },
            },
            {
                "type": "Feature",
                "properties": {
                    "eventtype": "WF",
                    "eventid": 1032994,
                    "alertlevel": "Green",
                    "country": "Australia",
                    "iso3": "AUS",
                    "fromdate": "2026-12-05T00:00:00",
                    "todate": "2026-12-09T00:00:00",
                    "description": "Green forest fire notification in Australia",
                    "affectedcountries": [{"iso3": "AUS", "countryname": "Australia"}],
                    "severitydata": {"severity": 5603.0, "severityunit": "ha"},
                },
            },
        ],
    }
)

MEASUREMENT = {
    "primary_source": 1,
    "scale": 1,
    "metric_source": "event",
    "station": "not applicable, this market measures the GDACS global disaster registry",
    "variable": "the number of qualifying disaster records",
    "unit": "count",
    "day_boundary": "the from and to dates of the record",
    "missing_data": "the market is voided if the registry answers with nothing at all",
    "match_terms": ["2026-12"],
    "event": {
        "publisher": "GDACS, the Joint Research Centre of the European Commission",
        "area": "Indonesia",
        "criteria": "a record counts when it is a flood, lists Indonesia among the affected countries and is orange or red",
        "require_citation": True,
        "match_terms": ["2026-12"],
        "count_rules": {
            "eventtype": ["FL"],
            "alertlevel": ["Orange", "Red"],
            "affected_iso3": ["IDN"],
        },
    },
}


def _market(contract, direct_vm, alice, bob, **overrides):
    direct_vm.sender = alice
    spec = json.loads(json.dumps(MEASUREMENT))
    spec["event"].update(overrides.pop("event", {}))
    market_id = create_market(
        contract,
        question="Will GDACS record at least 1 flood event affecting Indonesia in December 2026?",
        criteria="Count the qualifying records in the registry.",
        sources=(),
        event_urls=(GDACS_URL,),
        event_domains=("gdacs.org",),
        resolution_mode="metric",
        comparator=">=",
        threshold=1,
        metric_name="number of orange or red flood events affecting Indonesia",
        measurement=spec,
        **overrides,
    )
    bet(contract, direct_vm, bob, market_id, 0, 100 * GEN)
    # Both sides are backed, so the outcome that wins is always covered. A
    # market nobody backed the winner of is voided and refunded.
    bet(contract, direct_vm, bob, market_id, 1, 100 * GEN)
    warp_to(direct_vm, int(contract.get_market(market_id)["close_ts"]) + 60)
    return market_id


def _mock_registry(direct_vm, body: str = GDACS_BODY):
    direct_vm.mock_web(r"gdacs\.org", {"status": 200, "body": body})


def _mock_model(direct_vm, count_wrong: int = 99):
    """The model reports a number, and the contract ignores it."""
    direct_vm.mock_llm(
        r"Decide which outcome of the market is true|Answer the market question",
        json.dumps(
            {
                "resolved": True,
                "metric": str(count_wrong),
                "confidence": 90,
                "reasoning": "The registry lists the matching records.",
                "citations": [
                    {
                        "source_index": 1,
                        "quote": "Orange flood alert in Indonesia",
                    }
                ],
            }
        ),
    )


def test_the_contract_counts_the_records_itself(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _market(contract, direct_vm, direct_alice, direct_bob)

    _mock_registry(direct_vm)
    _mock_model(direct_vm, count_wrong=99)

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    # The model said ninety nine, the contract counted two.
    assert result["leader_reading"]["metric"] == 2
    assert result["consensus"]["outcome_index"] == 0
    assert contract.get_market(market_id)["metric_value"] == 2


def test_a_record_that_does_not_match_is_not_counted(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _market(
        contract,
        direct_vm,
        direct_alice,
        direct_bob,
        event={"count_rules": {"eventtype": ["TC"], "affected_iso3": ["IDN"]}},
    )

    _mock_registry(direct_vm)
    _mock_model(direct_vm)

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    # No tropical cyclone in the feed, so the count is zero.
    assert result["leader_reading"]["metric"] == 0
    assert result["consensus"]["outcome_index"] == 1


def test_the_severity_floor_is_applied(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _market(
        contract,
        direct_vm,
        direct_alice,
        direct_bob,
        event={
            "count_rules": {
                "eventtype": ["FL"],
                "affected_iso3": ["IDN"],
                "severity_min": 4000,
            }
        },
    )

    _mock_registry(direct_vm)
    _mock_model(direct_vm)

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    # Only the record with a severity of 4300 clears the floor.
    assert result["leader_reading"]["metric"] == 1


def test_a_market_without_count_rules_leaves_the_number_to_the_model(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _market(
        contract,
        direct_vm,
        direct_alice,
        direct_bob,
        event={"count_rules": {}},
    )

    _mock_registry(direct_vm)
    _mock_model(direct_vm, count_wrong=7)

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    # Without the rules the model is the one that counts.
    assert result["leader_reading"]["metric"] == 7


def test_a_count_rule_settlement_cannot_resolve_without_verified_citations(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """The contract counts, but a settlement has to be backed by a citation."""
    contract = deploy(direct_deploy)
    market_id = _market(contract, direct_vm, direct_alice, direct_bob)

    _mock_registry(direct_vm)
    direct_vm.mock_llm(
        r"Decide which outcome of the market is true|Answer the market question",
        json.dumps(
            {
                "resolved": True,
                "metric": 99,
                "confidence": 90,
                "reasoning": "The registry lists the matching records.",
                "citations": [],
                "uncited": True,
            }
        ),
    )

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)

    # The contract counted the records itself, but the settlement still has
    # to clear the citation check before it may resolve.
    assert result["consensus"]["resolved"] is False
    assert contract.get_market(market_id)["status"] == "voided"


def test_an_event_citation_keeps_the_event_source_url(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_deploy)
    market_id = _market(contract, direct_vm, direct_alice, direct_bob)

    _mock_registry(direct_vm)
    _mock_model(direct_vm, count_wrong=99)

    direct_vm.sender = direct_charlie
    result = contract.resolve_market(market_id)
    assert result["consensus"]["resolved"] is True

    trail = contract.get_citations(market_id)
    assert trail["trail"][0]["source_index"] == 1
    assert trail["trail"][0]["url"] == GDACS_URL
