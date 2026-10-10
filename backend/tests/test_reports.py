"""Reports: labelling, escaping, section selection and endpoint behaviour."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _report(client: TestClient, **overrides):  # type: ignore[no-untyped-def]
    body = {
        "dataset_id": "demo-synthetic-production-v1",
        "horizon_days": 30,
        "sections": ["overview", "forecast", "risk", "recommendations", "exploration", "sources"],
        "format": "html",
        "title": "Test report",
    }
    body.update(overrides)
    return client.post("/api/reports", json=body)


def test_html_report_labels_synthetic_data_and_value_types(client: TestClient) -> None:
    response = _report(client)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/html")
    assert "attachment" in response.headers["content-disposition"]
    html_text = response.text
    assert "SYNTHETIC DEMONSTRATION DATA" in html_text
    for label in ("Measured", "Forecast", "Probability", "Estimate", "Rule-based", "Index"):
        assert label in html_text
    assert "Not a resource or reserve statement" in html_text
    for heading in (
        "Overview",
        "Forecast and backtest",
        "Shortfall risk",
        "Recommendations",
        "Exploration zone",
        "Data sources",
    ):
        assert heading in html_text


def test_user_text_is_escaped(client: TestClient) -> None:
    response = _report(client, title="<script>alert(1)</script>", sections=["overview"])
    assert response.status_code == 200
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text


def test_only_requested_sections_are_included(client: TestClient) -> None:
    response = _report(client, sections=["overview"])
    assert "Overview" in response.text
    assert "Forecast and backtest" not in response.text
    assert "Exploration zone prioritisation" not in response.text


def test_json_report_carries_the_same_labels(client: TestClient) -> None:
    response = _report(client, format="json", sections=["overview", "risk"])
    assert response.status_code == 200
    body = response.json()
    assert body["report_version"] == "report-v1"
    assert body["dataset"]["is_synthetic"] is True
    assert body["sections"]["overview"]["value_type"] == "measured"
    assert body["sections"]["risk"]["value_type"] == "rule_based"
    assert set(body["value_type_legend"]) >= {"measured", "forecast", "probability", "estimate", "index"}


def test_unknown_sections_and_formats_are_rejected(client: TestClient) -> None:
    assert _report(client, sections=["overview", "admin"]).status_code == 422
    assert _report(client, format="pdf").status_code == 422
