"""Core API behaviour: health, readiness, CORS, error envelope and request ids."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_health_is_ok_and_does_not_need_dependencies(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "test"
    assert body["version"]


def test_readiness_reports_storage_and_demo_dataset(client: TestClient) -> None:
    response = client.get("/api/ready")
    assert response.status_code == 200
    checks = {c["name"]: c for c in response.json()["checks"]}
    assert checks["storage"]["status"] == "ok"
    assert checks["demo_dataset"]["status"] == "ok"
    assert checks["external_services"]["status"] == "degraded"  # disabled in tests
    assert response.json()["status"] == "ready"


def test_cors_allows_configured_origin_only(client: TestClient) -> None:
    allowed = client.options(
        "/api/overview",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"

    denied = client.options(
        "/api/overview",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in denied.headers


def test_cors_headers_are_present_on_error_responses(client: TestClient) -> None:
    response = client.get("/api/overview?mine_id=NOPE", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 422
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_unknown_route_uses_the_error_envelope(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert "traceback" not in response.text.lower()


def test_request_id_is_generated_and_echoed(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-Request-ID": "client-supplied-id-123"})
    assert response.headers["x-request-id"] == "client-supplied-id-123"
    rejected = client.get("/api/health", headers={"X-Request-ID": "bad id with spaces!!"})
    assert rejected.headers["x-request-id"] != "bad id with spaces!!"
    assert len(rejected.headers["x-request-id"]) >= 8


def test_unhandled_exceptions_return_safe_500(app: FastAPI) -> None:
    @app.get("/api/_boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail /var/lib/x")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/_boom")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["request_id"]
    assert "secret internal detail" not in response.text
    assert "Traceback" not in response.text


def test_validation_errors_do_not_echo_stack_traces(client: TestClient) -> None:
    response = client.get("/api/overview?start=not-a-date")
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_failed"
    assert isinstance(error["details"], list)
    assert "Traceback" not in response.text


def test_sources_registry_lists_public_sources_with_licences(client: TestClient) -> None:
    body = client.get("/api/meta/sources").json()
    ids = {s["id"] for s in body["sources"]}
    assert {"synthetic_production", "copernicus_sentinel2", "open_meteo_archive"} <= ids
    synthetic = next(s for s in body["sources"] if s["id"] == "synthetic_production")
    assert synthetic["source_type"] == "synthetic"
    copernicus = next(s for s in body["sources"] if s["id"] == "copernicus_sentinel2")
    assert "Copernicus" in copernicus["attribution"]
