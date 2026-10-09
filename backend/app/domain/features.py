"""Daily series and leakage-safe features for forecasting.

Leakage rules (tested in tests/test_features.py)
-----------------------------------------------
* Every feature for day *t* uses information dated **before** *t*, except:
  - ``plan``: the planned tonnage for day *t* is set in advance and is treated as known ex-ante;
  - calendar features (day of week, day of year), which are known in advance.
* The target for day *t* (actual tonnage) is never used in any feature for day *t*.
* Same-day operational values (downtime, weather and blasting hours, rainfall for day *t*)
  are **not** features. Only their lagged values are used.
* Scenario values used for future days (see forecasting.py) are explicit assumptions, not data.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.errors import InsufficientDataError

# operational column -> feature stem
OPERATIONAL_STEMS: dict[str, str] = {
    "equipment_downtime_h": "downtime",
    "weather_delay_h": "weather",
    "blasting_delay_h": "blasting",
    "rainfall_mm": "rain",
}

BASE_FEATURES: tuple[str, ...] = (
    "plan",
    "act_lag1",
    "act_lag2",
    "act_lag7",
    "act_roll7",
    "act_roll28",
    "att_roll7",
)
CALENDAR_FEATURES: tuple[str, ...] = ("dow_sin", "dow_cos", "doy_sin", "doy_cos")


@dataclass(frozen=True)
class Scope:
    """A forecasting scope: all mines, one mine (all its zones), or one zone."""

    mine_id: str | None = None
    zone_id: str | None = None

    @property
    def key(self) -> str:
        return f"{self.mine_id or 'ALL'}__{self.zone_id or 'ALL'}"

    @property
    def label(self) -> str:
        if self.zone_id:
            return f"Zone {self.zone_id}"
        if self.mine_id:
            return f"Mine {self.mine_id} (all zones)"
        return "All mines and zones"


def scope_rows(frame: pd.DataFrame, scope: Scope) -> pd.DataFrame:
    rows = frame
    if scope.mine_id:
        rows = rows[rows["mine_id"] == scope.mine_id]
    if scope.zone_id:
        rows = rows[rows["zone_id"] == scope.zone_id]
    return rows


def daily_series(frame: pd.DataFrame, scope: Scope) -> pd.DataFrame:
    """Aggregate the scope to one row per calendar day.

    ``actual`` is only defined on days where *every* zone row has an actual value.
    Partial days are left missing rather than summed, so no output is understated.
    Operational hours are averaged per zone-day, so units do not change with scope size.
    """
    rows = scope_rows(frame, scope)
    if rows.empty:
        raise InsufficientDataError("No production records match this scope.")
    days = pd.date_range(rows["date"].min(), rows["date"].max(), freq="D")
    grouped = rows.groupby("date")
    out = pd.DataFrame(index=days)
    out["n_rows"] = grouped.size().reindex(days).fillna(0).astype(int)
    out["n_actual"] = grouped["actual_production_t"].count().reindex(days).fillna(0).astype(int)
    out["plan"] = grouped["planned_production_t"].sum().reindex(days)
    actual_sum = grouped["actual_production_t"].sum(min_count=1).reindex(days)
    complete = (out["n_rows"] > 0) & (out["n_actual"] == out["n_rows"])
    out["actual"] = actual_sum.where(complete)
    for column in OPERATIONAL_STEMS:
        if column in rows.columns:
            out[column] = grouped[column].mean().reindex(days)
    out.index.name = "date"
    return out


def feature_names(series: pd.DataFrame) -> list[str]:
    names = list(BASE_FEATURES)
    for column, stem in OPERATIONAL_STEMS.items():
        if column in series.columns:
            names.extend([f"{stem}_lag1", f"{stem}_roll7"])
    names.extend(CALENDAR_FEATURES)
    return names


def build_features(series: pd.DataFrame) -> pd.DataFrame:
    """Compute features for every day in ``series`` using only earlier information."""
    actual = series["actual"]
    plan = series["plan"]
    feats = pd.DataFrame(index=series.index)
    feats["plan"] = plan
    feats["act_lag1"] = actual.shift(1)
    feats["act_lag2"] = actual.shift(2)
    feats["act_lag7"] = actual.shift(7)
    feats["act_roll7"] = actual.shift(1).rolling(7, min_periods=5).mean()
    feats["act_roll28"] = actual.shift(1).rolling(28, min_periods=20).mean()
    attainment = actual / plan
    feats["att_roll7"] = attainment.shift(1).rolling(7, min_periods=5).mean()
    for column, stem in OPERATIONAL_STEMS.items():
        if column in series.columns:
            feats[f"{stem}_lag1"] = series[column].shift(1)
            feats[f"{stem}_roll7"] = series[column].shift(1).rolling(7, min_periods=5).mean()
    dow = series.index.dayofweek.to_numpy()
    doy = series.index.dayofyear.to_numpy()
    feats["dow_sin"] = np.sin(2 * np.pi * dow / 7)
    feats["dow_cos"] = np.cos(2 * np.pi * dow / 7)
    feats["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    feats["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    return feats[feature_names(series)]
