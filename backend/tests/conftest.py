"""Shared fixtures. Every test gets an isolated data directory and offline settings."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

HEADER = (
    "date,mine_id,zone_id,planned_production_t,actual_production_t,"
    "equipment_downtime_h,weather_delay_h,blasting_delay_h,rainfall_mm"
)


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        log_level="WARNING",
        data_dir=tmp_path / "data",
        artifacts_dir=tmp_path / "artifacts",
        cors_origins="http://localhost:3000",
        enable_external_services=False,
        max_upload_mb=0.5,
        max_upload_rows=500,
        stale_data_days=14,
    )


@pytest.fixture()
def app(settings: Settings):  # type: ignore[no-untyped-def]
    return create_app(settings)


@pytest.fixture()
def client(app) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    with TestClient(app) as test_client:
        yield test_client


def csv_text(*lines: str, header: str = HEADER) -> bytes:
    return ("\n".join([header, *lines]) + "\n").encode("utf-8")
