import json
from pathlib import Path

from tic_data.models import OrganizationSelector, RateFilters
from tic_data.parser import extract_rates
from tic_data.toc import discover_in_network_files


def test_extract_by_tin_and_code(tmp_path: Path):
    source = tmp_path / "sample.json"
    source.write_text(json.dumps({
        "reporting_entity_name": "Example Payer",
        "reporting_entity_type": "health insurance issuer",
        "last_updated_on": "2026-08-01",
        "version": "2.0.0",
        "provider_references": [{
            "provider_group_id": 10,
            "network_name": ["Example PPO"],
            "provider_groups": [{
                "npi": [1234567890],
                "tin": {"type": "ein", "value": "12-3456789", "business_name": "Example PT LLC"}
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
                    "negotiated_rate": 42.50,
                    "expiration_date": "2026-12-31",
                    "service_code": ["11"],
                    "billing_class": "professional",
                    "setting": "outpatient"
                }]
            }]
        }]
    }), encoding="utf-8")

    result = extract_rates(
        source,
        OrganizationSelector(tins=["123456789"]),
        RateFilters(billing_codes=["97110"]),
    )
    assert result.metadata["reporting_entity_name"] == "Example Payer"
    assert result.matched_provider_group_ids == {10}
    assert result.rates[0]["negotiated_rate"] == 42.50


def test_embedded_provider_groups(tmp_path: Path):
    source = tmp_path / "embedded.json"
    source.write_text(json.dumps({
        "reporting_entity_name": "Example Payer",
        "in_network": [{
            "negotiation_arrangement": "ffs",
            "name": "Evaluation",
            "billing_code_type": "CPT",
            "billing_code_type_version": "2026",
            "billing_code": "97161",
            "description": "PT evaluation",
            "negotiated_rates": [{
                "provider_groups": [{
                    "npi": [1999999999],
                    "tin": {"type": "ein", "value": "98-7654321", "business_name": "Spoon Example"}
                }],
                "negotiated_prices": [{
                    "negotiated_type": "fee schedule",
                    "negotiated_rate": 100,
                    "expiration_date": "9999-12-31",
                    "billing_class": "professional",
                    "setting": "outpatient",
                    "service_code": ["11"]
                }]
            }]
        }]
    }), encoding="utf-8")
    result = extract_rates(source, OrganizationSelector(business_names=["spoon"]), RateFilters())
    assert len(result.rates) == 1
    assert result.rates[0]["billing_code"] == "97161"


def test_toc_discovery(tmp_path: Path):
    source = tmp_path / "toc.json"
    source.write_text(json.dumps({
        "reporting_structure": [{
            "reporting_plans": [{
                "plan_name": "Employer PPO",
                "issuer_name": "Example Payer",
                "plan_id_type": "ein",
                "plan_id": "11-1111111",
                "plan_sponsor_name": "Example Employer",
                "plan_market_type": "group"
            }],
            "in_network_files": [{
                "description": "rates",
                "location": "https://example.com/in-network.json.gz"
            }]
        }]
    }), encoding="utf-8")
    rows = discover_in_network_files(source, plan_sponsor_name="Example Employer")
    assert rows[0]["location"].endswith(".json.gz")
