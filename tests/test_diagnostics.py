import json
from pathlib import Path

from tic_data.models import OrganizationSelector, RateFilters
from tic_data.parser import extract_rates


def _sample(path: Path) -> Path:
    path.write_text(json.dumps({
        "reporting_entity_name": "Diagnostic Payer",
        "provider_references": [{
            "provider_group_id": 10,
            "provider_groups": [{
                "npi": [1234567890],
                "tin": {"type": "ein", "value": "123456789", "business_name": "Example PT"}
            }]
        }],
        "in_network": [{
            "negotiation_arrangement": "ffs",
            "name": "Therapeutic exercises",
            "billing_code_type": "CPT",
            "billing_code_type_version": "2026",
            "billing_code": "97110",
            "description": "Therapeutic exercises",
            "negotiated_rates": [{
                "provider_references": [10],
                "negotiated_prices": [{
                    "negotiated_type": "negotiated",
                    "negotiated_rate": 50,
                    "expiration_date": "2027-01-01",
                    "billing_class": "institutional",
                    "service_code": ["11"]
                }]
            }]
        }]
    }), encoding="utf-8")
    return path


def test_tin_with_or_without_dash_matches_same_file_value(tmp_path: Path):
    source = _sample(tmp_path / "sample.json")
    plain = extract_rates(source, OrganizationSelector(tins=["123456789"]), RateFilters(billing_classes=[]))
    dashed = extract_rates(source, OrganizationSelector(tins=["12-3456789"]), RateFilters(billing_classes=[]))
    assert plain.matched_provider_group_ids == {10}
    assert dashed.matched_provider_group_ids == {10}
    assert dashed.diagnostics["normalized_organization"]["tins"] == ["123456789"]


def test_diagnostics_explain_missing_code(tmp_path: Path):
    source = _sample(tmp_path / "sample.json")
    result = extract_rates(
        source,
        OrganizationSelector(tins=["12-3456789"]),
        RateFilters(billing_codes=["97530"], billing_code_types=["CPT"], billing_classes=[]),
    )
    assert result.rates == []
    assert result.diagnostics["provider_groups_matched"] == 1
    assert result.diagnostics["requested_billing_codes_seen"] == []
    assert result.diagnostics["in_network_items_scanned"] == 1


def test_diagnostics_explain_billing_class_filter(tmp_path: Path):
    source = _sample(tmp_path / "sample.json")
    result = extract_rates(
        source,
        OrganizationSelector(tins=["123456789"]),
        RateFilters(
            billing_codes=["97110"],
            billing_code_types=["CPT"],
            billing_classes=["professional"],
        ),
    )
    assert result.rates == []
    assert result.diagnostics["requested_billing_codes_seen"] == ["97110"]
    assert result.diagnostics["negotiated_rate_groups_linked_to_provider"] == 1
    assert result.diagnostics["negotiated_prices_matched_filters"] == 0
    assert result.diagnostics["billing_classes_seen_for_linked_rates"] == ["institutional"]
