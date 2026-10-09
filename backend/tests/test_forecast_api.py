"""Forecast and risk endpoints: wiring, caching, persistence, scope validation and insufficient data."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.features import Scope
from app.domain.forecast_service import ForecastService
from app.domain.store import DatasetStore
from app.domain.synthetic import DEMO_DATASET_ID
from app.main import create_app
from tests.conftest import csv_text

ALLOWED_VERDICTS = {"beats_best_baseline", "worse_than_best_baseline", "no_reliable_difference"}
MODEL_NAMES = {"plan", "persistence", "seasonal_naive_7", "moving_average_7", "gradient_boosting", "ridge"}


@pytest.fixture(scope="module")
def api(tmp_path_factory):  # type: ignore[no-untyped-def]
    tmp = tmp_path_factory.mktemp("forecast-api")
    settings = Settings(
        app_env="test",
        log_level="WARNING",
        data_dir=tmp / "data",
        artifacts_dir=tmp / "artifacts",
        cors_origins="http://localhost:3000",
        enable_external_services=False,
        max_upload_mb=2.0,
        max_upload_rows=5000,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        yield client, settings


def _long_user_csv(days: int, zone: str = "U1-Z1", mine: str = "U1") -> bytes:
    rng = np.random.default_rng(3)
    start = pd.Timestamp("2024-01-01")
    lines = []
    for day in range(days):
        plan = 1000.0 + 50 * np.sin(day / 58.0)
        actual = plan * float(np.clip(rng.normal(0.92, 0.04), 0.5, 1.1))
        date = (start + pd.Timedelta(days=day)).date().isoformat()
        lines.append(f"{date},{mine},{zone},{plan:.1f},{actual:.1f},3,1,0.5,0")
    return csv_text(*lines)


def test_forecast_for_demo_all_scope_has_all_models_and_horizon(api) -> None:  # type: ignore[no-untyped-def]
    client, _ = api
    response = client.get("/api/forecast", params={"horizon_days": 30})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dataset"]["is_synthetic"] is True
    assert "SYNTHETIC" in body["dataset"]["banner"]
    assert body["model"]["value_kind"] == "forecast"
    assert body["model"]["source"] == "trained"
    names = {m["name"] for m in body["evaluation"]["models"]}
    assert names == MODEL_NAMES
    assert body["evaluation"]["verdict"] in ALLOWED_VERDICTS
    assert body["evaluation"]["n_evaluated_days"] > 0
    assert len(body["evaluation"]["folds"]) == 3
    assert body["classification"]["value_kind"] == "probability"
    forecast = body["forecast"]
    assert forecast["forecast_days"] == 30
    assert forecast["days"][0]["date"] == "2026-10-01"
    assert forecast["days"][-1]["date"] == "2026-10-30"
    assert all(day["interval_low_t"] <= day["forecast_t"] <= day["interval_high_t"] for day in forecast["days"])
    assert body["drivers"]["forecast_drivers"]
    assert body["value_kinds"]["gap_t"] == "estimate"


def test_second_request_is_served_from_memory(api) -> None:  # type: ignore[no-untyped-def]
    client, _ = api
    body = client.get("/api/forecast").json()
    assert body["model"]["source"] == "memory"


def test_restarted_service_reloads_the_saved_model(api) -> None:  # type: ignore[no-untyped-def]
    client, settings = api
    store: DatasetStore = client.app.state.store  # type: ignore[attr-defined]
    fresh = ForecastService(store, settings.artifacts_dir, horizon_days=30)
    _model, _series, source = fresh.model_for(DEMO_DATASET_ID, Scope())
    assert source == "loaded"


def test_risk_endpoint_matches_forecast_totals(api) -> None:  # type: ignore[no-untyped-def]
    client, _ = api
    forecast = client.get("/api/forecast", params={"mine_id": "SYN-A"}).json()
    risk = client.get("/api/risk", params={"mine_id": "SYN-A"}).json()
    totals = forecast["forecast"]["totals"]
    assert risk["expected"]["net_gap_t"] == totals["net_gap_t"]
    assert risk["expected"]["plan_t"] == totals["plan_t"]
    assert risk["expected"]["value_kind"] == "estimate"
    assert risk["band"]["level"] in {"high", "medium", "low"}
    assert risk["band"]["value_kind"] == "rule_based"
    assert risk["shortfall_probability"]["value_kind"] == "probability"
    assert risk["classification_check"]["verdict"] in {
        "beats_base_rate",
        "no_skill_over_base_rate",
        "not_evaluable",
    }
    assert any("policy" in item.lower() for item in risk["limitations"])


def test_scope_validation_rejects_unknown_and_mismatched_zones(api) -> None:  # type: ignore[no-untyped-def]
    client, _ = api
    unknown_mine = client.get("/api/forecast", params={"mine_id": "NOPE"})
    assert unknown_mine.status_code == 422
    assert unknown_mine.json()["error"]["details"]["valid_mines"]
    mismatch = client.get("/api/forecast", params={"mine_id": "SYN-B", "zone_id": "SYN-A-Z1"})
    assert mismatch.status_code == 422
    assert "does not belong" in mismatch.json()["error"]["message"]


def test_horizon_bounds_are_enforced(api) -> None:  # type: ignore[no-untyped-def]
    client, _ = api
    assert client.get("/api/forecast", params={"horizon_days": 3}).status_code == 422
    assert client.get("/api/forecast", params={"horizon_days": 120}).status_code == 422


def test_small_upload_gets_a_clear_insufficient_data_error(api) -> None:  # type: ignore[no-untyped-def]
    client, _ = api
    upload = client.post(
        "/api/datasets",
        files={"file": ("short.csv", _long_user_csv(days=60), "text/csv")},
    )
    assert upload.status_code == 201, upload.text
    dataset_id = upload.json()["id"]
    response = client.get("/api/forecast", params={"dataset_id": dataset_id})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "insufficient_data"
    assert "Not enough complete days" in error["message"]
    assert error["details"]["required_days"] == 450


def test_changed_data_invalidates_the_saved_model(api) -> None:  # type: ignore[no-untyped-def]
    client, settings = api
    store: DatasetStore = client.app.state.store  # type: ignore[attr-defined]
    upload = client.post(
        "/api/datasets",
        files={"file": ("long.csv", _long_user_csv(days=520), "text/csv")},
    )
    assert upload.status_code == 201, upload.text
    dataset_id = upload.json()["id"]
    scope = Scope(zone_id="U1-Z1")
    fresh = ForecastService(store, settings.artifacts_dir, horizon_days=30)
    _m, _s, first = fresh.model_for(dataset_id, scope)
    assert first == "trained"

    restarted = ForecastService(store, settings.artifacts_dir, horizon_days=30)
    _m, _s, second = restarted.model_for(dataset_id, scope)
    assert second == "loaded"

    data_file = settings.data_dir / "datasets" / dataset_id / "data.csv"
    lines = data_file.read_text(encoding="utf-8").splitlines()
    fields = lines[200].split(",")
    assert fields[3] != "1234.5"
    fields[3] = "1234.5"  # change one planned value in the stored file
    lines[200] = ",".join(fields)
    data_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    changed = ForecastService(store, settings.artifacts_dir, horizon_days=30)
    _m, _s, third = changed.model_for(dataset_id, scope)
    assert third == "trained"


def test_forecast_and_risk_reject_a_non_production_dataset_id(api) -> None:  # type: ignore[no-untyped-def]
    client, _ = api
    assert client.get("/api/forecast", params={"dataset_id": "missing-dataset"}).status_code == 404
    assert client.get("/api/risk", params={"dataset_id": "../etc"}).status_code == 404
