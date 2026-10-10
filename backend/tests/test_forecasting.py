"""Forecasting: splits, baselines, metrics, bootstrap, persistence and insufficient-data errors."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from app.domain import forecasting as fc
from app.domain.features import Scope, daily_series
from app.domain.synthetic import generate_production_frame
from app.errors import InsufficientDataError

NOW = datetime(2026, 10, 9, tzinfo=UTC)


@pytest.fixture(scope="module")
def demo_frame() -> pd.DataFrame:
    frame = generate_production_frame()
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


@pytest.fixture(scope="module")
def mine_a_model(demo_frame: pd.DataFrame):  # type: ignore[no-untyped-def]
    scope = Scope(mine_id="SYN-A")
    series = daily_series(demo_frame, scope)
    config = fc.TrainingConfig()
    fingerprint = fc.scope_fingerprint(demo_frame, scope, config)
    model = fc.train_forecaster(series, scope=scope, dataset_id="demo", fingerprint=fingerprint, config=config, now=NOW)
    return model, series


def test_metric_definitions_match_hand_calculation() -> None:
    y = np.array([10.0, 12.0, 8.0])
    p = np.array([9.0, 15.0, 8.0])
    assert fc._mae(y, p) == pytest.approx((1 + 3 + 0) / 3)
    assert fc._rmse(y, p) == pytest.approx(np.sqrt((1 + 9 + 0) / 3))


def test_fold_windows_are_contiguous_and_end_on_last_date() -> None:
    last = pd.Timestamp("2026-09-30")
    windows = fc.fold_windows(last, folds=3, test_days=90)
    assert windows[-1][1] == last
    for (_start_a, end_a), (start_b, _end_b) in itertools.pairwise(windows):
        assert start_b == end_a + pd.Timedelta(days=1)
    assert all((end - start).days == 89 for start, end in windows)


def test_training_only_uses_days_before_each_test_window(mine_a_model) -> None:  # type: ignore[no-untyped-def]
    model, _series = mine_a_model
    for row in model.fold_table:
        assert pd.Timestamp(row["train_end"]) < pd.Timestamp(row["test_start"])
        assert row["train_days"] >= model.config.min_train_days
    oos = model.oos
    assert oos.index.is_monotonic_increasing
    assert not oos.index.duplicated().any()


def test_baselines_are_exactly_their_definitions(mine_a_model) -> None:  # type: ignore[no-untyped-def]
    model, series = mine_a_model
    oos = model.oos
    day = oos.index[len(oos) // 2]
    actual = series["actual"]
    assert oos.loc[day, "base_persistence"] == pytest.approx(actual.loc[day - pd.Timedelta(days=1)])
    assert oos.loc[day, "base_seasonal_naive_7"] == pytest.approx(actual.loc[day - pd.Timedelta(days=7)])
    assert oos.loc[day, "base_plan"] == pytest.approx(series.loc[day, "plan"])
    trailing = actual.loc[day - pd.Timedelta(days=7) : day - pd.Timedelta(days=1)]
    assert oos.loc[day, "base_moving_average_7"] == pytest.approx(trailing.mean())


def test_reported_mae_matches_recomputation_from_predictions(mine_a_model) -> None:  # type: ignore[no-untyped-def]
    model, _ = mine_a_model
    oos = model.oos
    table = {row["name"]: row for row in model.metrics["models"]}
    assert table["plan"]["mae"] == pytest.approx(round(fc._mae(oos["actual"].values, oos["base_plan"].values), 2))
    assert table["gradient_boosting"]["mae"] == pytest.approx(
        round(fc._mae(oos["actual"].values, oos["pred_gradient_boosting"].values), 2)
    )
    assert table["gradient_boosting"]["n"] == len(oos) == table["plan"]["n"]


def test_bootstrap_difference_is_zero_for_identical_errors_and_deterministic() -> None:
    errors = np.abs(np.random.default_rng(1).normal(0, 5, 200))
    first = fc.block_bootstrap_difference(errors, errors)
    second = fc.block_bootstrap_difference(errors, errors)
    assert first == second
    assert first["estimate"] == 0.0 and first["ci_low"] == 0.0 and first["ci_high"] == 0.0


def test_bootstrap_detects_a_clearly_better_model() -> None:
    rng = np.random.default_rng(2)
    base = np.abs(rng.normal(20, 2, 300))
    better = base * 0.5
    result = fc.block_bootstrap_difference(better, base)
    assert result["estimate"] < 0 and result["ci_high"] < 0


def test_classification_metrics_agree_with_sklearn(mine_a_model) -> None:  # type: ignore[no-untyped-def]
    model, _ = mine_a_model
    oos = model.oos
    expected_auc = roc_auc_score(oos["short"], oos["p_short"])
    reported = model.metrics["classification"]["roc_auc"]
    assert reported == pytest.approx(round(expected_auc, 3))


def test_insufficient_data_is_a_clear_422_style_error() -> None:
    frame = generate_production_frame()
    frame["date"] = pd.to_datetime(frame["date"])
    short = frame[frame["date"] < pd.Timestamp("2023-06-30")]
    scope = Scope(zone_id="SYN-A-Z1")
    series = daily_series(short, scope)
    config = fc.TrainingConfig()
    with pytest.raises(InsufficientDataError) as info:
        fc.train_forecaster(series, scope=scope, dataset_id="x", fingerprint="f", config=config, now=NOW)
    assert "Not enough complete days" in str(info.value)
    assert info.value.status_code == 422
    assert info.value.code == "insufficient_data"
    assert info.value.details["required_days"] == config.min_train_days + config.folds * config.test_days


def test_save_and_reload_reproduces_predictions(tmp_path, mine_a_model) -> None:  # type: ignore[no-untyped-def]
    model, series = mine_a_model
    path = fc.save_forecaster(model, tmp_path)
    loaded = fc.load_forecaster(path)
    assert loaded is not None
    assert loaded.fingerprint == model.fingerprint
    before = fc.forecast_forward(series, model, 30)
    after = fc.forecast_forward(series, loaded, 30)
    assert before["days"] == after["days"]
    assert before["totals"] == after["totals"]


def test_reload_refuses_files_that_are_not_forecasters(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bogus = tmp_path / "bogus.joblib"
    bogus.write_bytes(b"not a model")
    assert fc.load_forecaster(bogus) is None
    assert fc.load_forecaster(tmp_path / "missing.joblib") is None


def test_forward_forecast_uses_plan_and_documents_scenario(mine_a_model) -> None:  # type: ignore[no-untyped-def]
    model, series = mine_a_model
    result = fc.forecast_forward(series, model, 30)
    assert result["forecast_days"] == 30
    days = [row["date"] for row in result["days"]]
    assert days[0] == "2026-10-01" and days[-1] == "2026-10-30"
    plan_from_data = series.loc["2026-10-01":"2026-10-30", "plan"].round(1).tolist()
    assert [row["plan_t"] for row in result["days"]] == plan_from_data
    totals = result["totals"]
    assert totals["net_gap_t"] == pytest.approx(totals["forecast_t"] - totals["plan_t"], abs=0.2)
    assert result["scenario_assumptions"]["window_days"] == fc.SCENARIO_WINDOW_DAYS
    assert set(result["scenario_assumptions"]["values"]) >= {"equipment_downtime_h", "weather_delay_h"}


def test_forward_forecast_truncates_where_plan_is_missing(demo_frame: pd.DataFrame) -> None:
    frame = demo_frame.copy()
    scope = Scope(mine_id="SYN-A")
    config = fc.TrainingConfig()
    series = daily_series(frame, scope)
    model = fc.train_forecaster(series, scope=scope, dataset_id="d", fingerprint="f", config=config, now=NOW)
    series_missing = series.copy()
    series_missing.loc["2026-10-05", "plan"] = np.nan
    result = fc.forecast_forward(series_missing, model, 30)
    assert result["forecast_days"] == 4
    assert result["truncated_reason"] and "2026-10-05" in result["truncated_reason"]


def test_shortfall_classifier_targets_material_shortfall_days(mine_a_model) -> None:  # type: ignore[no-untyped-def]
    model, series = mine_a_model
    day = model.oos.index[10]
    expected = float(series.loc[day, "actual"] < series.loc[day, "plan"] * 0.95)
    assert model.oos.loc[day, "short"] == expected
