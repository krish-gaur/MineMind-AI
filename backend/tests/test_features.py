"""Leakage guarantees for forecasting features.

A feature for day t must never depend on the target or on same-day operational values
for day t, nor on anything dated after t. These tests perturb data and check that the
feature rows do not move.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.domain.features import OPERATIONAL_STEMS, Scope, build_features, daily_series, feature_names

OPS = list(OPERATIONAL_STEMS)


def _series(days: int = 80, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2026-01-01", periods=days, freq="D", name="date")
    frame = pd.DataFrame(index=index)
    frame["plan"] = 1000.0 + rng.normal(0, 20, days)
    frame["actual"] = frame["plan"] * rng.uniform(0.8, 1.05, days)
    frame["equipment_downtime_h"] = rng.uniform(0, 8, days)
    frame["weather_delay_h"] = rng.uniform(0, 6, days)
    frame["blasting_delay_h"] = rng.uniform(0, 4, days)
    frame["rainfall_mm"] = rng.uniform(0, 30, days)
    return frame


def test_features_for_day_t_ignore_same_day_target_and_operations() -> None:
    base = _series()
    t = pd.Timestamp("2026-02-20")
    before = build_features(base)
    changed = base.copy()
    changed.loc[t, "actual"] = 1.0  # target for day t
    for column in OPS:
        changed.loc[t, column] = 999.0  # same-day operational value
    after = build_features(changed)
    pd.testing.assert_series_equal(before.loc[t], after.loc[t], check_names=False)


def test_features_do_not_depend_on_later_days() -> None:
    base = _series()
    cutoff = pd.Timestamp("2026-02-10")
    before = build_features(base)
    changed = base.copy()
    later = changed.index > cutoff
    changed.loc[later, ["actual", *OPS]] = changed.loc[later, ["actual", *OPS]] * 3.0 + 50.0
    after = build_features(changed)
    pd.testing.assert_frame_equal(before.loc[:cutoff], after.loc[:cutoff])


def test_feature_names_have_no_same_day_operational_columns() -> None:
    names = feature_names(_series())
    assert len(names) == len(set(names))
    for stem in OPERATIONAL_STEMS.values():
        assert f"{stem}_lag1" in names and f"{stem}_roll7" in names
        assert stem not in names  # only lagged or rolled versions are used


def test_lag_and_rolling_definitions_are_exact() -> None:
    series = _series(days=30)
    feats = build_features(series)
    day = pd.Timestamp("2026-01-20")
    previous = series.loc[:"2026-01-19", "actual"]
    assert feats.loc[day, "act_lag1"] == pytest.approx(previous.iloc[-1])
    assert feats.loc[day, "act_lag2"] == pytest.approx(previous.iloc[-2])
    assert feats.loc[day, "act_lag7"] == pytest.approx(previous.iloc[-7])
    assert feats.loc[day, "act_roll7"] == pytest.approx(previous.iloc[-7:].mean())
    attainment = (series["actual"] / series["plan"]).loc[:"2026-01-19"]
    assert feats.loc[day, "att_roll7"] == pytest.approx(attainment.iloc[-7:].mean())
    assert feats.loc[day, "plan"] == pytest.approx(series.loc[day, "plan"])


def test_calendar_features_are_bounded_and_periodic() -> None:
    feats = build_features(_series())
    for column in ("dow_sin", "dow_cos", "doy_sin", "doy_cos"):
        assert feats[column].abs().max() <= 1.0 + 1e-12


def test_daily_series_is_strict_about_partial_days(sample_frame: pd.DataFrame) -> None:
    all_scope = daily_series(sample_frame, Scope())
    # The sample has a day where one zone has no actual: the aggregate must be missing, not understated.
    partial_day = pd.Timestamp("2026-03-02")
    assert pd.isna(all_scope.loc[partial_day, "actual"])
    assert all_scope.loc[partial_day, "plan"] == pytest.approx(2000.0)
    complete_day = pd.Timestamp("2026-03-01")
    assert all_scope.loc[complete_day, "actual"] == pytest.approx(1800.0)


@pytest.fixture()
def sample_frame() -> pd.DataFrame:
    rows = [
        ("2026-03-01", "M1", "Z1", 1000.0, 900.0),
        ("2026-03-01", "M1", "Z2", 1000.0, 900.0),
        ("2026-03-02", "M1", "Z1", 1000.0, 950.0),
        ("2026-03-02", "M1", "Z2", 1000.0, np.nan),
    ]
    frame = pd.DataFrame(
        rows,
        columns=["date", "mine_id", "zone_id", "planned_production_t", "actual_production_t"],
    )
    frame["date"] = pd.to_datetime(frame["date"])
    for column in OPS:
        frame[column] = 1.0
    return frame
