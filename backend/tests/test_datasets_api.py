"""Dataset API: listing, preview, upload security, validation errors and deletion."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.domain.synthetic import DEMO_DATASET_ID
from tests.conftest import csv_text

VALID_ROWS = [
    "2026-09-01,SYN-A,SYN-A-Z1,1000,950,2,0,0,0",
    "2026-09-02,SYN-A,SYN-A-Z1,1000,,2,0,0,0",
]


def _upload(client: TestClient, content: bytes, filename: str = "production.csv", **data: str):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/datasets",
        files={"file": (filename, content, "text/csv")},
        data=data,
    )


def test_demo_dataset_is_listed_as_synthetic(client: TestClient) -> None:
    response = client.get("/api/datasets")
    assert response.status_code == 200
    datasets = {d["id"]: d for d in response.json()["datasets"]}
    demo = datasets[DEMO_DATASET_ID]
    assert demo["source_type"] == "synthetic"
    assert demo["is_synthetic"] is True
    assert demo["deletable"] is False
    assert "SYNTHETIC" in demo["source_label"]


def test_dataset_detail_carries_provenance_and_validation(client: TestClient) -> None:
    body = client.get(f"/api/datasets/{DEMO_DATASET_ID}").json()
    assert body["provenance"]["source_type"] == "synthetic"
    assert "SYNTHETIC" in body["provenance"]["label"]
    assert body["validation"]["status"] == "valid_with_warnings"
    assert body["sha256"]


def test_preview_returns_rows_with_nulls_as_null(client: TestClient) -> None:
    body = client.get(f"/api/datasets/{DEMO_DATASET_ID}/preview?rows=5").json()
    assert body["returned_rows"] == 5
    assert body["total_rows"] > 5
    assert "date" in body["columns"]
    assert all(isinstance(row["date"], str) for row in body["rows"])


def test_valid_upload_is_stored_as_user_provided(client: TestClient) -> None:
    response = _upload(client, csv_text(*VALID_ROWS), name="Pilot extract")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source_type"] == "user_provided"
    assert body["is_synthetic"] is False
    assert body["deletable"] is True
    assert body["name"] == "Pilot extract"
    assert body["original_filename"] == "production.csv"
    assert body["validation"]["status"] == "valid_with_warnings"

    listed = {d["id"] for d in client.get("/api/datasets").json()["datasets"]}
    assert body["id"] in listed


def test_invalid_upload_returns_422_with_report_and_stores_nothing(client: TestClient, settings) -> None:  # type: ignore[no-untyped-def]
    before = {d["id"] for d in client.get("/api/datasets").json()["datasets"]}
    response = _upload(client, csv_text("2026-99-01,SYN-A,SYN-A-Z1,1000,950,2,0,0,0"))
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_failed"
    assert error["details"]["status"] == "invalid"
    after = {d["id"] for d in client.get("/api/datasets").json()["datasets"]}
    assert before == after


def test_non_csv_extension_is_rejected(client: TestClient) -> None:
    response = _upload(client, csv_text(*VALID_ROWS), filename="production.xlsx")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


def test_oversized_upload_is_rejected_before_parsing(client: TestClient, settings) -> None:  # type: ignore[no-untyped-def]
    limit = settings.max_upload_bytes
    padding = "x" * (limit + 10)
    content = ("date,mine_id,zone_id,planned_production_t,actual_production_t\n" + padding).encode()
    response = _upload(client, content)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_upload_filename_cannot_escape_the_data_directory(client: TestClient, settings) -> None:  # type: ignore[no-untyped-def]
    response = _upload(client, csv_text(*VALID_ROWS), filename="../../../../etc/passwd.csv")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["original_filename"] == "passwd.csv"
    dataset_dir = Path(settings.data_dir) / "datasets" / body["id"]
    assert dataset_dir.is_dir()
    assert not (Path(settings.data_dir).parent / "etc").exists()


def test_unsafe_dataset_ids_are_not_found(client: TestClient) -> None:
    for bad in ("..", "x", "A_B", "%2e%2e", "demo;rm"):
        response = client.get(f"/api/datasets/{bad}")
        assert response.status_code == 404, bad


def test_only_user_datasets_can_be_deleted(client: TestClient) -> None:
    forbidden = client.delete(f"/api/datasets/{DEMO_DATASET_ID}")
    assert forbidden.status_code == 403
    created = _upload(client, csv_text(*VALID_ROWS)).json()
    deleted = client.delete(f"/api/datasets/{created['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/datasets/{created['id']}").status_code == 404


def test_schema_endpoint_documents_the_contract(client: TestClient) -> None:
    body = client.get("/api/datasets/schema/production").json()
    names = [c["name"] for c in body["columns"]]
    assert names[:5] == ["date", "mine_id", "zone_id", "planned_production_t", "actual_production_t"]
    assert body["accepted_extensions"] == [".csv"]
    assert "planned_production_t" in body["example_csv"]


def test_export_returns_the_normalised_csv(client: TestClient) -> None:
    response = client.get(f"/api/datasets/{DEMO_DATASET_ID}/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.text.splitlines()[0].startswith("date,mine_id,zone_id")
