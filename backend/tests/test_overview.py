"""Overview KPIs: exact arithmetic on a hand-built table, filters, freshness and API wiring."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.domain.kpis import ProductionFilter, apply_filter, compute_overview
from app.domain.synthetic import DEMO_DATASET_ID
from app.domain.validation import validate_production_csv
from tests.conftest import csv_text


def _frame() -> pd.DataFrame:
    rows = [
        # date,        mine,  zone,   plan, actual, dt,  wd,  bd, rain
        ("2026-09-01", "M1", "Z1", 100.0, 90.0, 9.0, 0.0, 0.0, 0.0),
        ("2026-09-02", "M1", "Z1", 100.0, 110.0, 1.0, 0.0, 5.0, 0.0),
        ("2026-09-03", "M1", "Z1", 100.0, np.nan, 2.0, 7.0, 0.0, 12.0),  # pending actual
        ("2026-09-01", "M2", "Z2", 50.0, 50.0, 0.0, 0.0, 0.0, 0.0),
    ]
    frame = pd.DataFrame(
        rows,
        columns=[
            "date",
            "mine_id",
            "zone_id",
            "planned_production_t",
            "actual_production_t",
            "equipment_downtime_h",
            "weather_delay_h",
            "blasting_delay_h",
            "rainfall_mm",
        ],
    )
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def test_kpis_are_computed_on_matched_days_only() -> None:
    result = compute_overview(_frame(), ProductionFilter(), as_of=date(2026, 9, 10), stale_days=14)
    kpis = result["kpis"]
    # Matched rows: 3 (M1 day1, M1 day2, M2 day1). Pending M1 day3 is excluded from gap maths.
    assert kpis["planned_t"] == 250.0
    assert kpis["actual_t"] == 250.0
    assert kpis["gap_t"] == 0.0
    assert kpis["variance_pct"] == 0.0
    assert kpis["attainment_pct"] == 100.0
    assert kpis["coverage_pct"] == 75.0  # 3 of 4 rows have actuals
    # Day 1 M1 is below plan, day 2 is above, the M2 day equals plan: 1 of 3 matched days below.
    assert kpis["days_below_plan_pct"] == pytest.approx(33.33, abs=0.01)


def test_gap_and_variance_follow_the_sign_convention() -> None:
    frame = _frame()
    frame.loc[frame["mine_id"] == "M2", "actual_production_t"] = 40.0  # shortfall of 10 on plan 50
    result = compute_overview(frame, ProductionFilter(), as_of=date(2026, 9, 10), stale_days=14)
    assert result["kpis"]["gap_t"] == -10.0
    assert result["kpis"]["variance_pct"] == pytest.approx(-4.0)
    assert result["kpis"]["attainment_pct"] == pytest.approx(96.0)


def test_downtime_and_constraint_shares() -> None:
    result = compute_overview(_frame(), ProductionFilter(), as_of=date(2026, 9, 10), stale_days=14)
    by_key = {item["key"]: item for item in result["constraints"]}
    assert by_key["equipment_downtime"]["total_hours"] == 12.0  # 9 + 1 + 2 + 0
    assert by_key["weather_delay"]["total_hours"] == 7.0
    assert by_key["blasting_delay"]["total_hours"] == 5.0
    total_share = sum(item["share_pct"] for item in result["constraints"])
    assert total_share == pytest.approx(100.0, abs=0.2)
    assert by_key["equipment_downtime"]["days_over_threshold"] == 1  # only the 9 h day exceeds 8 h


def test_filters_by_mine_zone_and_dates() -> None:
    frame = _frame()
    only_m1 = apply_filter(frame, ProductionFilter(mine_id="M1"))
    assert set(only_m1["mine_id"]) == {"M1"}
    windowed = apply_filter(frame, ProductionFilter(start=date(2026, 9, 2), end=date(2026, 9, 2)))
    assert len(windowed) == 1
    zoned = apply_filter(frame, ProductionFilter(zone_id="Z2"))
    assert set(zoned["zone_id"]) == {"Z2"}


def test_empty_selection_returns_empty_flag_and_no_kpis() -> None:
    result = compute_overview(
        _frame(),
        ProductionFilter(mine_id="M2", start=date(2030, 1, 1)),
        as_of=date(2026, 9, 10),
        stale_days=14,
    )
    assert result["empty"] is True
    assert result["kpis"]["planned_t"] is None
    assert result["kpis"]["variance_pct"] is None
    assert result["constraints"] == [] or all(item["records"] == 0 for item in result["constraints"])


def test_freshness_flags_stale_data() -> None:
    fresh = compute_overview(_frame(), ProductionFilter(), as_of=date(2026, 9, 10), stale_days=14)
    assert fresh["freshness"]["status"] == "fresh"
    assert fresh["freshness"]["days_since_last_actual"] == 8
    stale = compute_overview(_frame(), ProductionFilter(), as_of=date(2026, 12, 1), stale_days=14)
    assert stale["freshness"]["status"] == "stale"


def test_zone_table_is_sorted_by_gap_and_matches_totals() -> None:
    result = compute_overview(_frame(), ProductionFilter(), as_of=date(2026, 9, 10), stale_days=14)
    zones = result["zones"]
    assert [z["zone_id"] for z in zones] == ["Z1", "Z2"]
    z1 = zones[0]
    assert z1["pending_rows"] == 1
    assert z1["planned_t"] == 200.0
    assert z1["actual_t"] == 200.0


def test_overview_api_matches_independent_recomputation(client: TestClient, settings) -> None:  # type: ignore[no-untyped-def]
    """Recompute the demo KPIs straight from the stored CSV and compare with the API."""
    body = client.get("/api/overview").json()
    csv_path = settings.data_dir / "datasets" / DEMO_DATASET_ID / "data.csv"
    raw = pd.read_csv(csv_path, parse_dates=["date"])
    matched = raw[raw["actual_production_t"].notna()]
    expected_planned = round(float(matched["planned_production_t"].sum()), 1)
    expected_actual = round(float(matched["actual_production_t"].sum()), 1)
    assert body["kpis"]["planned_t"] == pytest.approx(expected_planned, abs=0.05)
    assert body["kpis"]["actual_t"] == pytest.approx(expected_actual, abs=0.05)
    assert body["kpis"]["gap_t"] == pytest.approx(expected_actual - expected_planned, abs=0.1)
    assert body["dataset"]["is_synthetic"] is True
    assert "SYNTHETIC DEMONSTRATION DATA" in body["dataset"]["banner"]
    assert any("SYNTHETIC" in note for note in body["notes"])


def test_overview_rejects_inverted_date_range_and_unknown_zone(client: TestClient) -> None:
    inverted = client.get("/api/overview?start=2026-09-10&end=2026-09-01")
    assert inverted.status_code == 422
    unknown_zone = client.get("/api/overview?zone_id=NOPE")
    assert unknown_zone.status_code == 422
    assert "valid_zones" in unknown_zone.json()["error"]["details"]


def test_overview_works_for_a_user_upload(client: TestClient) -> None:
    rows = [
        "2026-09-01,U1,U1-Z1,100,90,1,0,0,0",
        "2026-09-02,U1,U1-Z1,100,95,1,0,0,0",
        "2026-09-03,U1,U1-Z1,100,101,0,0,0,0",
    ]
    upload = client.post(
        "/api/datasets",
        files={"file": ("u1.csv", csv_text(*rows), "text/csv")},
    )
    assert upload.status_code == 201, upload.text
    dataset_id = upload.json()["id"]
    body = client.get("/api/overview", params={"dataset_id": dataset_id}).json()
    assert body["dataset"]["is_synthetic"] is False
    assert body["dataset"]["banner"] is None
    assert body["kpis"]["planned_t"] == 300.0
    assert body["kpis"]["actual_t"] == 286.0
    assert body["kpis"]["gap_t"] == -14.0


def test_validate_frame_helpers_are_consistent() -> None:
    outcome = validate_production_csv(csv_text("2026-09-01,A,A1,10,9,0,0,0,0"), max_rows=10)
    assert outcome.frame is not None
    assert outcome.report.rows_with_actual == 1
