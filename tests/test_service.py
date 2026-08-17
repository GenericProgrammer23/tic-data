from fastapi.testclient import TestClient

from tic_data.service import app


def test_home_ui_and_health():
    client = TestClient(app)
    page = client.get("/")
    assert page.status_code == 200
    assert "Load a payer index" in page.text
    assert "Direct rate-file upload" in page.text
    assert "12-3456789 or 123456789" in page.text
    assert 'id="codeInput"' in page.text
    assert 'id="codeChips"' in page.text
    assert "Troubleshooting details" in page.text
    assert client.get("/health").json() == {"status": "ok"}
