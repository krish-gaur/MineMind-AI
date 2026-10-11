"""Recommendation rules: triggers, non-triggers, impact arithmetic and API wiring."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.domain.features import Scope
from app.domain.recommendations import build_recommendations

AS_OF = date(2026, 9, 28)
TODAY = date(2026, 10, 9)
RULE_IDS = {
    "data_freshness",
    "equipment_recurrence",
    "production_deviation",
    "monsoon_weather",
    "blasting_delay",
    "zone_concentration",
    "data_completeness",
    "forecast_gap",
    "model_governance",
}


def _designed_frame(*, clean: bool = False) -> pd.DataFrame:
    """Two zones over 151 days ending on AS_OF. Z2 alternates heavy-downtime and normal days."""
    days = pd.date_range("2026-05-01", AS_OF.isoformat(), freq="D")
    rows = []
    for index, day in enumerate(days):
        if clean:
            rows.append(("M1", "Z1", day, 1000.0, 1000.0, 1.0, 0.0, 0.0, 0.0))
            rows.append(("M1", "Z2", day, 1000.0, 1000.0, 1.0, 0.0, 0.0, 0.0))
            continue
        heavy = index % 2 == 0
        rows.append(("M1", "Z1", day, 1000.0, 995.0, 1.0, 0.0, 0.0, 0.0))
        rows.append(("M1", "Z2", day, 1000.0, 800.0 if heavy else 990.0, 10.0 if heavy else 2.0, 0.0, 0.0, 0.0))
    frame = pd.DataFrame(
        rows,
        columns=[
            "mine_id",
            "zone_id",
            "date",
            "planned_production_t",
            "actual_production_t",
            "equipment_downtime_h",
            "weather_delay_h",
            "blasting_delay_h",
            "rainfall_mm",
        ],
    )
    return frame


def _by_id(result: dict) -> dict[str, dict]:  # type: ignore[type-arg]
    return {item["id"]: item for item in result["recommendations"]}


def test_designed_data_fires_the_expected_rules_with_exact_impact() -> None:
    result = build_recommendations(_designed_frame(), Scope(mine_id="M1"), today=TODAY, stale_days=14, risk=None)
    fired = _by_id(result)
    assert {"REC-EQUIP-Z2", "REC-PROD-DEVIATION", "REC-FOCUS-Z2"} <= set(fired)
    assert "REC-WEATHER-MONSOON" not in fired  # no weather delay recorded at all
    assert "REC-DATA-CAPTURE" not in fired  # every row has an actual
    assert "REC-DATA-FRESHNESS" not in fired  # 11 days old, threshold 14

    equipment = fired["REC-EQUIP-Z2"]
    assert equipment["priority"] == "high"  # 14 of 28 zone-days (50%) are heavy
    impact = equipment["expected_impact"]
    assert impact["status"] == "estimated"
    # Normal-day mean 990 t minus heavy-day mean 800 t = 190 t/day, times 14 heavy days in the window.
    assert impact["value_t"] == 2660.0
    assert "association" in impact["basis"]
    assert equipment["value_kind"] == "rule_based"

    production = fired["REC-PROD-DEVIATION"]
    attainment = next(e["value"] for e in production["evidence"] if e["metric"] == "Attainment")
    assert attainment == round((995 + (800 + 990) / 2) / 2000 * 100, 1)  # 2 zones x 1000 t planned = 94.5
    assert production["priority"] == "medium"
    assert production["expected_impact"]["status"] == "not_estimated"


def test_zone_concentration_points_at_the_zone_carrying_the_shortfall() -> None:
    result = build_recommendations(_designed_frame(), Scope(mine_id="M1"), today=TODAY, stale_days=14, risk=None)
    focus = _by_id(result)["REC-FOCUS-Z2"]
    assert focus["zone_id"] == "Z2"
    share = next(e["value"] for e in focus["evidence"] if e["metric"] == "Share of shortfall tonnes")
    assert share > 90


def test_clean_data_triggers_nothing_and_says_so() -> None:
    result = build_recommendations(_designed_frame(clean=True), Scope(), today=TODAY, stale_days=14, risk=None)
    assert result["recommendations"] == []
    assert {rule["rule_id"] for rule in result["rules"]} == RULE_IDS
    assert all(rule["fired"] is False for rule in result["rules"])
    assert any("rules" in note.lower() for note in result["notes"])


def test_stale_data_fires_only_after_the_threshold() -> None:
    fresh = build_recommendations(_designed_frame(clean=True), Scope(), today=TODAY, stale_days=14, risk=None)
    assert "REC-DATA-FRESHNESS" not in _by_id(fresh)
    stale = build_recommendations(
        _designed_frame(clean=True), Scope(), today=date(2026, 12, 1), stale_days=14, risk=None
    )
    rec = _by_id(stale)["REC-DATA-FRESHNESS"]
    assert rec["priority"] == "medium"
    assert rec["evidence"][0]["value"] == (date(2026, 12, 1) - AS_OF).days


def test_missing_actuals_trigger_the_data_capture_rule() -> None:
    frame = _designed_frame(clean=True)
    frame.loc[frame.index[: len(frame) // 3], "actual_production_t"] = np.nan
    frame.loc[frame.index[-20:], "actual_production_t"] = np.nan
    result = build_recommendations(frame, Scope(), today=TODAY, stale_days=14, risk=None)
    rec = _by_id(result)["REC-DATA-CAPTURE"]
    assert "pending" in rec["summary"]
    assert rec["expected_impact"]["status"] == "not_estimated"


def test_blasting_delays_name_the_weekday() -> None:
    frame = _designed_frame(clean=True)
    dates = pd.to_datetime(frame["date"])
    frame["blasting_delay_h"] = np.where(dates.dt.day_name() == "Friday", 5.0, 0.5)
    result = build_recommendations(frame, Scope(), today=TODAY, stale_days=14, risk=None)
    rec = _by_id(result)["REC-BLAST-DELAY"]
    assert "Fridays" in rec["summary"]


def test_forecast_rules_use_the_risk_output_explicitly() -> None:
    risk = {
        "expected": {"plan_t": 10000.0, "forecast_t": 9000.0, "net_gap_t": -1000.0, "net_gap_pct": -10.0},
        "band": {"level": "high"},
        "horizon": {"forecast_days": 10, "start": "2026-10-01", "end": "2026-10-10"},
        "model_check": {
            "regression_verdict": "no_reliable_difference",
            "regression_text": "",
            "classifier_verdict": "not_evaluable",
        },
        "classification_check": {"verdict": "not_evaluable", "brier_skill_pct": None, "n": 100},
        "limitations": [],
    }
    result = build_recommendations(_designed_frame(clean=True), Scope(), today=TODAY, stale_days=14, risk=risk)
    fired = _by_id(result)
    recovery = fired["REC-FORECAST-RECOVERY"]
    assert recovery["priority"] == "high"
    assert recovery["expected_impact"]["status"] == "estimated"
    assert recovery["expected_impact"]["value_t"] == 1000.0
    assert "100 t per day" in recovery["expected_impact"]["basis"]
    assert "REC-MODEL-RELIABILITY" in fired


def test_no_actuals_means_no_rules_are_evaluated() -> None:
    frame = _designed_frame(clean=True)
    frame["actual_production_t"] = np.nan
    result = build_recommendations(frame, Scope(), today=TODAY, stale_days=14, risk=None)
    assert result["recommendations"] == []
    assert result["as_of"] is None
    assert "No recorded actuals" in result["notes"][0]


def test_recommendations_endpoint_returns_evidence_for_every_item(client: TestClient) -> None:
    response = client.get("/api/recommendations", params={"include_forecast": "false"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert {rule["rule_id"] for rule in body["rules"]} == RULE_IDS
    assert body["as_of"] == "2026-09-30"
    priorities = [item["priority"] for item in body["recommendations"]]
    assert priorities == sorted(priorities, key=["high", "medium", "low"].index)
    for item in body["recommendations"]:
        assert item["evidence"], item["id"]
        assert item["expected_impact"]["status"] in {"estimated", "not_estimated"}
        assert item["suggested_actions"], item["id"]
        assert item["confidence"]["level"] in {"low", "medium"}
