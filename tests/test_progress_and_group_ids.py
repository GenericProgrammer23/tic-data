import json
import time
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

import tic_data.service as service
from tic_data.models import OrganizationSelector, RateFilters
from tic_data.parser import extract_rates


def _sample_payload(provider_reference):
    return {
        "reporting_entity_name": "Cigna-like Payer",
        "provider_references": [{
            "provider_group_id": 847392,
            "network_name": ["National PPO"],
            "provider_groups": [{
                "npi": [1234567890],
                "tin": {
                    "type": "ein",
                    "value": "12-3456789",
                    "business_name": "Example Therapy LLC",
                },
            }],
        }],
        "in_network": [{
            "negotiation_arrangement": "ffs",
            "name": "Therapeutic exercises",
            "billing_code_type": "CPT",
            "billing_code_type_version": "2026",
            "billing_code": "97110",
            "description": "Therapeutic exercises",
            "negotiated_rates": [{
                "provider_references": [provider_reference],
                "negotiated_prices": [{
                    "negotiated_type": "negotiated",
                    "negotiated_rate": 52.18,
                    "expiration_date": "2027-01-01",
                    "service_code": ["11"],
                    "billing_class": "professional",
                    "setting": "outpatient",
                }],
            }],
        }],
    }


def test_provider_group_id_matches_number_to_string(tmp_path: Path):
    source = tmp_path / "rates.json"
    source.write_text(json.dumps(_sample_payload("847392")), encoding="utf-8")

    result = extract_rates(
        source,
        OrganizationSelector(tins=["123456789"]),
        RateFilters(
            billing_codes=["97110"],
            billing_code_types=["CPT"],
            billing_classes=["professional"],
        ),
    )

    assert result.matched_provider_group_ids == {847392}
    assert result.diagnostics["matched_provider_group_ids"] == [847392]
    assert result.diagnostics["negotiated_rate_groups_linked_to_provider"] == 1
    assert float(result.rates[0]["negotiated_rate"]) == 52.18


def test_parser_emits_named_progress_stages(tmp_path: Path):
    source = tmp_path / "rates.json"
    source.write_text(json.dumps(_sample_payload(847392)), encoding="utf-8")
    events = []

    extract_rates(
        source,
        OrganizationSelector(tins=["12-3456789"]),
        RateFilters(billing_codes=["97110"]),
        progress_callback=lambda percent, stage, message, details: events.append(
            (percent, stage, message, details)
        ),
    )

    stages = [event[1] for event in events]
    assert "Reading metadata" in stages
    assert "Finding provider groups" in stages
    assert "Finding negotiated rates" in stages
    assert stages[-1] == "Complete"
    assert events[-1][0] == 100


def test_url_extraction_job_reports_progress_and_result(tmp_path: Path, monkeypatch):
    source = tmp_path / "rates.json"
    source.write_text(json.dumps(_sample_payload("847392")), encoding="utf-8")

    @contextmanager
    def fake_local_source_from_url(url, **kwargs):
        callback = kwargs.get("progress_callback")
        if callback:
            callback(50, 100)
            callback(100, 100)
        yield source

    monkeypatch.setattr(service, "local_source_from_url", fake_local_source_from_url)
    client = TestClient(service.app)

    created = client.post(
        "/extract/jobs",
        json={
            "url": "https://example.com/national-ppo.json.gz",
            "organization": {"tins": ["12-3456789"]},
            "filters": {
                "billing_codes": ["97110"],
                "billing_code_types": ["CPT"],
                "billing_classes": ["professional"],
            },
        },
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    job = None
    for _ in range(100):
        response = client.get(f"/extract/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"complete", "error"}:
            break
        time.sleep(0.01)

    assert job is not None
    assert job["status"] == "complete"
    assert job["step"] == 4
    assert job["percent"] == 100
    assert job["stage"] == "Complete"
    assert job["result"]["rate_count"] == 1
    assert job["result"]["matched_provider_group_ids"] == [847392]


def test_home_contains_progress_ui():
    client = TestClient(service.app)
    page = client.get("/")
    assert page.status_code == 200
    assert 'id="progressPanel"' in page.text
    assert "Match provider groups" in page.text
    assert "Scan negotiated rates" in page.text
