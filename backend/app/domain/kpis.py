"""Executive KPIs computed from the selected production records.

Definitions (all computed here, never hard-coded):

* **Matched days** - rows that have both a plan and a recorded actual. Gap and
  attainment compare like with like: plan and actual are summed over matched rows
  only, so pending days cannot make the variance look worse or better.
* **Gap (t)** - actual minus plan over matched rows. Negative means shortfall.
* **Variance (%)** - gap divided by plan over matched rows.
* **Attainment (%)** - actual divided by plan over matched rows.
* **Coverage (%)** - share of rows in the period that have an actual value.
* **Heavy-constraint day** - a zone-day whose constraint hours exceed the policy
  threshold in :mod:`app.domain.policy`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from app.domain import policy
from app.domain.provenance import ValueKind

CONSTRAINTS: tuple[tuple[str, str, str, float], ...] = (
    ("equipment_downtime", "Equipment downtime", "equipment_downtime_h", policy.DOWNTIME_HEAVY_DAY_H),
    ("weather_delay", "Weather delay", "weather_delay_h", policy.WEATHER_HEAVY_DAY_H),
    ("blasting_delay", "Blasting delay", "blasting_delay_h", policy.BLASTING_HEAVY_DAY_H),
)


@dataclass(frozen=True)
class ProductionFilter:
    start: date | None = None
    end: date | None = None
    mine_id: str | None = None
    zone_id: str | None = None


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


def apply_filter(frame: pd.DataFrame, flt: ProductionFilter) -> pd.DataFrame:
    out = frame
    if flt.mine_id:
        out = out[out["mine_id"] == flt.mine_id]
    if flt.zone_id:
        out = out[out["zone_id"] == flt.zone_id]
    if flt.start:
        out = out[out["date"] >= pd.Timestamp(flt.start)]
    if flt.end:
        out = out[out["date"] <= pd.Timestamp(flt.end)]
    return out


def available_scope(frame: pd.DataFrame, flt: ProductionFilter) -> tuple[date | None, date | None]:
    """Date bounds to show when the user did not specify them."""
    start = flt.start or (frame["date"].min().date() if len(frame) else None)
    end = flt.end or (frame["date"].max().date() if len(frame) else None)
    return start, end


def _kpis(filtered: pd.DataFrame, matched: pd.DataFrame) -> dict[str, Any]:
    rows = len(filtered)
    rows_with_actual = len(matched)
    planned = float(matched["planned_production_t"].sum()) if rows_with_actual else None
    actual = float(matched["actual_production_t"].sum()) if rows_with_actual else None
    gap = (actual - planned) if (actual is not None and planned is not None) else None
    variance = gap / planned * 100.0 if (gap is not None and planned) else None
    attainment = actual / planned * 100.0 if (actual is not None and planned) else None
    coverage = (rows_with_actual / rows * 100.0) if rows else None
    days_below = None
    if rows_with_actual:
        days_below = float((matched["actual_production_t"] < matched["planned_production_t"]).mean() * 100.0)

    downtime = (
        filtered["equipment_downtime_h"].dropna() if "equipment_downtime_h" in filtered else pd.Series(dtype=float)
    )
    downtime_mean = float(downtime.mean()) if len(downtime) else None
    heavy_pct = float((downtime > policy.DOWNTIME_HEAVY_DAY_H).mean() * 100.0) if len(downtime) else None
    return {
        "planned_t": _round(planned, 1),
        "actual_t": _round(actual, 1),
        "gap_t": _round(gap, 1),
        "variance_pct": _round(variance),
        "attainment_pct": _round(attainment),
        "coverage_pct": _round(coverage),
        "days_below_plan_pct": _round(days_below),
        "equipment_downtime_h_total": _round(float(downtime.sum()) if len(downtime) else None),
        "equipment_downtime_h_per_zone_day": _round(downtime_mean),
        "equipment_downtime_days_over_threshold_pct": _round(heavy_pct),
        "value_kind": ValueKind.MEASURED.value,
    }


def _constraints(filtered: pd.DataFrame) -> list[dict[str, Any]]:
    totals: list[tuple[str, str, str, float, pd.Series]] = []
    for key, label, column, threshold in CONSTRAINTS:
        if column not in filtered:
            continue
        totals.append((key, label, column, threshold, filtered[column].dropna()))
    grand_total = sum(float(values.sum()) for *_, values in totals)
    items: list[dict[str, Any]] = []
    for key, label, column, threshold, values in totals:
        total = float(values.sum())
        items.append(
            {
                "key": key,
                "label": label,
                "column": column,
                "total_hours": _round(total, 1),
                "share_pct": _round(total / grand_total * 100.0, 1) if grand_total else None,
                "mean_hours_per_zone_day": _round(float(values.mean()) if len(values) else None, 2),
                "records": len(values),
                "threshold_hours": threshold,
                "days_over_threshold": int((values > threshold).sum()),
                "value_kind": ValueKind.MEASURED.value,
            }
        )
    items.sort(key=lambda item: item["total_hours"] or 0.0, reverse=True)
    return items


def _monthly(matched: pd.DataFrame, filtered: pd.DataFrame) -> list[dict[str, Any]]:
    if matched.empty:
        return []
    matched_month = matched["date"].dt.strftime("%Y-%m")
    grouped = matched.assign(month=matched_month).groupby("month", sort=True)
    planned = grouped["planned_production_t"].sum()
    actual = grouped["actual_production_t"].sum()
    records = grouped.size()
    result: list[dict[str, Any]] = []
    downtime_by_month: pd.Series = pd.Series(dtype=float)
    if "equipment_downtime_h" in filtered:
        downtime_by_month = (
            filtered.assign(month=filtered["date"].dt.strftime("%Y-%m")).groupby("month")["equipment_downtime_h"].mean()
        )
    for month in planned.index:
        plan_m = float(planned.loc[month])
        act_m = float(actual.loc[month])
        result.append(
            {
                "month": str(month),
                "planned_t": _round(plan_m, 1),
                "actual_t": _round(act_m, 1),
                "gap_t": _round(act_m - plan_m, 1),
                "attainment_pct": _round(act_m / plan_m * 100.0) if plan_m else None,
                "records_with_actual": int(records.loc[month]),
                "equipment_downtime_h_mean": _round(_finite(downtime_by_month.get(month))),
            }
        )
    return result


def _zones(filtered: pd.DataFrame, matched: pd.DataFrame) -> list[dict[str, Any]]:
    if filtered.empty:
        return []
    keys = ["mine_id", "zone_id"]
    matched_sums = matched.groupby(keys)[["planned_production_t", "actual_production_t"]].sum()
    records = filtered.groupby(keys).size()
    pending = filtered.assign(pending=filtered["actual_production_t"].isna()).groupby(keys)["pending"].sum()
    totals = filtered.groupby(keys).agg(
        downtime=("equipment_downtime_h", "sum"),
        weather=("weather_delay_h", "sum"),
        blasting=("blasting_delay_h", "sum"),
    )
    rows: list[dict[str, Any]] = []
    for mine_id, zone_id in records.index:
        key = (mine_id, zone_id)
        plan_m = float(matched_sums.loc[key, "planned_production_t"]) if key in matched_sums.index else 0.0
        act_m = float(matched_sums.loc[key, "actual_production_t"]) if key in matched_sums.index else 0.0
        has_match = key in matched_sums.index
        rows.append(
            {
                "mine_id": mine_id,
                "zone_id": zone_id,
                "records": int(records.loc[key]),
                "pending_rows": int(pending.loc[key]),
                "planned_t": _round(plan_m, 1) if has_match else None,
                "actual_t": _round(act_m, 1) if has_match else None,
                "gap_t": _round(act_m - plan_m, 1) if has_match else None,
                "variance_pct": _round((act_m - plan_m) / plan_m * 100.0) if has_match and plan_m else None,
                "attainment_pct": _round(act_m / plan_m * 100.0) if has_match and plan_m else None,
                "equipment_downtime_h_total": _round(_finite(totals.loc[key, "downtime"]), 1),
                "weather_delay_h_total": _round(_finite(totals.loc[key, "weather"]), 1),
                "blasting_delay_h_total": _round(_finite(totals.loc[key, "blasting"]), 1),
            }
        )
    rows.sort(key=lambda r: r["gap_t"] if r["gap_t"] is not None else 0.0)
    return rows


def freshness(frame: pd.DataFrame, as_of: date, stale_days: int) -> dict[str, Any]:
    dated = frame.loc[frame["actual_production_t"].notna(), "date"]
    if dated.empty:
        return {
            "last_actual_date": None,
            "days_since_last_actual": None,
            "stale_threshold_days": stale_days,
            "status": "unknown",
            "as_of": as_of,
        }
    last = dated.max().date()
    days = (as_of - last).days
    return {
        "last_actual_date": last,
        "days_since_last_actual": days,
        "stale_threshold_days": stale_days,
        "status": "stale" if days > stale_days else "fresh",
        "as_of": as_of,
    }


def compute_overview(
    frame: pd.DataFrame,
    flt: ProductionFilter,
    *,
    as_of: date,
    stale_days: int,
) -> dict[str, Any]:
    """Compute every overview figure for the filtered selection."""
    filtered = apply_filter(frame, flt)
    matched = filtered[filtered["actual_production_t"].notna()]
    start, end = available_scope(frame, flt)
    period = {
        "start": start,
        "end": end,
        "rows": len(filtered),
        "rows_with_actual": len(matched),
        "rows_pending_actual": int(len(filtered) - len(matched)),
        "series": int(filtered.groupby(["mine_id", "zone_id"]).ngroups) if len(filtered) else 0,
        "days": int((end - start).days + 1) if start and end else 0,
    }
    return {
        "empty": bool(filtered.empty),
        "period": period,
        "kpis": _kpis(filtered, matched),
        "constraints": _constraints(filtered),
        "monthly": _monthly(matched, filtered),
        "zones": _zones(filtered, matched),
        "freshness": freshness(frame, as_of, stale_days),
    }
