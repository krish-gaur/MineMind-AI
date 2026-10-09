"""Evidence-driven recommendations.

Every recommendation comes from an explicit, documented rule that reads the dataset (and, for
the planning rule, the forecast/risk output). A rule only fires when its evidence threshold is
met, and the response also lists the rules that were checked and did not fire, so an empty
list is never silent.

Expected impact is either:
* ``estimated`` - an arithmetic estimate with the basis stated (for example, the difference in
  mean output between heavy-downtime and normal days, times the number of heavy days). These are
  associations in the data, not causal effects.
* ``not_estimated`` - the evidence does not support a number (for example, weather mitigation).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import pandas as pd

from app.domain import policy
from app.domain.features import Scope, scope_rows

MONSOON_MONTHS = (6, 7, 8, 9)
MIN_EVENTS_FOR_ESTIMATE = 10


@dataclass
class RuleResult:
    rule_id: str
    title: str
    fired: bool
    reason: str
    recommendation: dict[str, Any] | None = None
    checks: list[dict[str, Any]] = field(default_factory=list)


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(float(value), digits)


def _evidence(metric: str, value: Any, unit: str, period: str, value_kind: str = "measured") -> dict[str, Any]:
    return {"metric": metric, "value": value, "unit": unit, "period": period, "value_kind": value_kind}


def _window(rows: pd.DataFrame, as_of: date, days: int) -> tuple[pd.DataFrame, date]:
    start = as_of - timedelta(days=days - 1)
    window = rows[(rows["date"] >= pd.Timestamp(start)) & (rows["date"] <= pd.Timestamp(as_of))]
    return window, start


def _sum_or_none(values: pd.Series) -> float | None:
    values = values.dropna()
    return float(values.sum()) if len(values) else None


# ----------------------------------------------------------------------------
# Rules
# ----------------------------------------------------------------------------
def rule_equipment_recurrence(rows: pd.DataFrame, as_of: date) -> RuleResult:
    rule_id, title = "equipment_recurrence", "Recurring equipment downtime"
    window, start = _window(rows, as_of, policy.RECENT_WINDOW_DAYS)
    period = f"{start.isoformat()} to {as_of.isoformat()}"
    checks: list[dict[str, Any]] = []
    best: tuple[str, float, pd.DataFrame] | None = None
    for zone_id, zone_window in window.groupby("zone_id"):
        downtime = zone_window["equipment_downtime_h"].dropna()
        if len(downtime) < 8:
            continue
        share = float((downtime > policy.DOWNTIME_HEAVY_DAY_H).mean() * 100.0)
        checks.append({"zone_id": zone_id, "heavy_day_share_pct": _round(share, 1), "days": len(downtime)})
        if share >= policy.RECURRENCE_SHARE_PCT and (best is None or share > best[1]):
            best = (str(zone_id), share, zone_window)
    if best is None:
        return RuleResult(
            rule_id,
            title,
            False,
            f"No zone had {policy.DOWNTIME_HEAVY_DAY_H:g}+ hour downtime days on at least "
            f"{policy.RECURRENCE_SHARE_PCT:g}% of zone-days in the last {policy.RECENT_WINDOW_DAYS} days.",
            checks=checks,
        )

    zone_id, share, zone_window = best
    zone_all = rows[rows["zone_id"] == zone_id]
    evidence_rows = zone_all[zone_all["equipment_downtime_h"].notna() & zone_all["actual_production_t"].notna()]
    heavy_hist = evidence_rows[evidence_rows["equipment_downtime_h"] > policy.DOWNTIME_HEAVY_DAY_H]
    normal_hist = evidence_rows[evidence_rows["equipment_downtime_h"] <= policy.DOWNTIME_HEAVY_DAY_H]
    heavy_days_window = int((zone_window["equipment_downtime_h"] > policy.DOWNTIME_HEAVY_DAY_H).sum())
    impact: dict[str, Any] = {
        "status": "not_estimated",
        "value_t": None,
        "unit": "t",
        "basis": "Too few heavy-downtime or normal days with recorded actuals to compare output.",
    }
    if len(heavy_hist) >= MIN_EVENTS_FOR_ESTIMATE and len(normal_hist) >= MIN_EVENTS_FOR_ESTIMATE:
        difference = float(normal_hist["actual_production_t"].mean() - heavy_hist["actual_production_t"].mean())
        estimate = max(0.0, difference) * heavy_days_window
        impact = {
            "status": "estimated",
            "value_t": _round(estimate, 0),
            "unit": "t",
            "basis": (
                f"Mean output on normal-downtime days minus heavy-downtime days in this zone's history "
                f"({difference:,.0f} t per day), times the {heavy_days_window} heavy day(s) in the window. "
                "This is an association in the data, not a measured effect of removing downtime."
            ),
        }
    priority = "high" if share >= 50.0 else "medium"
    recommendation: dict[str, Any] = {
        "id": f"REC-EQUIP-{zone_id}",
        "title": f"Review recurring equipment downtime in zone {zone_id}",
        "priority": priority,
        "category": "maintenance",
        "zone_id": zone_id,
        "summary": (
            f"{share:.0f}% of zone-days in the last {policy.RECENT_WINDOW_DAYS} days had more than "
            f"{policy.DOWNTIME_HEAVY_DAY_H:g} hours of equipment downtime."
        ),
        "reasoning": (
            "Repeated heavy-downtime days point to a recurring equipment or maintenance problem rather than "
            "one-off failures, and they are a material constraint on output in this zone."
        ),
        "suggested_actions": [
            f"Pull the breakdown log for {zone_id} for the last 90 days and group failures by equipment and cause.",
            "Check whether repeated failures share a component, operator shift or maintenance interval.",
            "Agree a preventive maintenance or spares plan for the top recurring cause before the next monsoon.",
        ],
        "evidence": [
            _evidence("Heavy-downtime zone-days", heavy_days_window, "days", period),
            _evidence("Share of zone-days above threshold", _round(share, 1), "%", period),
            _evidence(
                "Mean equipment downtime",
                _round(float(zone_window.loc[zone_window["zone_id"] == zone_id, "equipment_downtime_h"].mean()), 2),
                "h per zone-day",
                period,
            ),
            _evidence(
                "Total equipment downtime",
                _round(_sum_or_none(zone_window.loc[zone_window["zone_id"] == zone_id, "equipment_downtime_h"]), 1),
                "h",
                period,
            ),
        ],
        "expected_impact": impact,
        "confidence": _confidence(len(heavy_hist) >= MIN_EVENTS_FOR_ESTIMATE, len(zone_window)),
        "limitations": [
            "The dataset does not record failure causes or equipment IDs.",
            "Output differences are associations and may reflect other conditions on heavy-downtime days.",
        ],
    }
    return RuleResult(rule_id, title, True, recommendation["summary"], recommendation, checks)


def rule_production_deviation(rows: pd.DataFrame, as_of: date) -> RuleResult:
    rule_id, title = "production_deviation", "Persistent production shortfall"
    window, start = _window(rows, as_of, policy.RECENT_WINDOW_DAYS)
    matched = window[window["actual_production_t"].notna()]
    period = f"{start.isoformat()} to {as_of.isoformat()}"
    if matched.empty:
        return RuleResult(rule_id, title, False, "No recorded actuals in the recent window.")
    planned = float(matched["planned_production_t"].sum())
    actual = float(matched["actual_production_t"].sum())
    attainment = actual / planned * 100.0 if planned else math.nan
    below_share = float((matched["actual_production_t"] < matched["planned_production_t"]).mean() * 100.0)
    checks = [{"attainment_pct": _round(attainment, 1), "days_below_plan_pct": _round(below_share, 1)}]
    if not (attainment < policy.ATTAINMENT_TARGET_PCT and below_share >= policy.SHORTFALL_DAYS_SHARE_PCT):
        return RuleResult(
            rule_id,
            title,
            False,
            f"Attainment {attainment:.1f}% in the last {policy.RECENT_WINDOW_DAYS} days, with "
            f"{below_share:.0f}% of days "
            f"below plan. Neither trips the deviation rule (below {policy.ATTAINMENT_TARGET_PCT:g}% and "
            f"at least {policy.SHORTFALL_DAYS_SHARE_PCT:g}% of days below plan).",
            checks=checks,
        )
    gap = actual - planned
    priority = "high" if attainment < 90.0 else "medium"
    recommendation: dict[str, Any] = {
        "id": "REC-PROD-DEVIATION",
        "title": "Investigate the persistent production shortfall against plan",
        "priority": priority,
        "category": "production",
        "zone_id": None,
        "summary": (
            f"Attainment is {attainment:.1f}% against a {policy.ATTAINMENT_TARGET_PCT:g}% target, and "
            f"{below_share:.0f}% of matched days were below plan."
        ),
        "reasoning": (
            "A shortfall on most days, rather than on a few outliers, suggests the plan is out of step with "
            "demonstrated output or that a common constraint is being missed."
        ),
        "suggested_actions": [
            "Hold a daily plan-versus-actual review with a root-cause code for every shortfall day.",
            "Test whether the plan is achievable: compare it with the trailing 28-day output by zone.",
            "Start with the zone that contributes most of the gap (see the zone-concentration recommendation, if any).",
        ],
        "evidence": [
            _evidence("Attainment", _round(attainment, 1), "%", period),
            _evidence("Gap to plan on matched days", _round(gap, 0), "t", period),
            _evidence("Days below plan", _round(below_share, 1), "%", period),
            _evidence("Matched days", len(matched), "days", period),
        ],
        "expected_impact": {
            "status": "not_estimated",
            "value_t": None,
            "unit": "t",
            "basis": "Closing the gap depends on which causes the review finds, so no impact is estimated.",
        },
        "confidence": _confidence(True, len(matched)),
        "limitations": ["Gap is measured on matched days only. Pending days are excluded."],
    }
    return RuleResult(rule_id, title, True, recommendation["summary"], recommendation, checks)


def rule_monsoon_weather(rows: pd.DataFrame, as_of: date) -> RuleResult:
    rule_id, title = "monsoon_weather", "Monsoon weather exposure"
    scoped = rows[rows["weather_delay_h"].notna()]
    monsoon = scoped[scoped["date"].dt.month.isin(MONSOON_MONTHS)]
    dry = scoped[~scoped["date"].dt.month.isin(MONSOON_MONTHS)]
    checks: list[dict[str, Any]] = [{"monsoon_records": len(monsoon), "other_records": len(dry)}]
    if len(monsoon) < 30 or len(dry) < 30 or float(dry["weather_delay_h"].mean()) <= 0:
        return RuleResult(
            rule_id, title, False, "Not enough monsoon and non-monsoon records with weather delay data.", checks=checks
        )
    ratio = float(monsoon["weather_delay_h"].mean() / dry["weather_delay_h"].mean())
    checks[0]["ratio"] = _round(ratio, 2)
    if ratio < policy.WEATHER_MONSOON_RATIO:
        return RuleResult(
            rule_id,
            title,
            False,
            f"Weather delay in June to September is {ratio:.1f} times the rest of the year, below the "
            f"{policy.WEATHER_MONSOON_RATIO:g} times trigger.",
            checks=checks,
        )
    recommendation: dict[str, Any] = {
        "id": "REC-WEATHER-MONSOON",
        "title": "Plan the monsoon season around weather stoppages",
        "priority": "medium",
        "category": "planning",
        "zone_id": None,
        "summary": f"Weather delay is {ratio:.1f} times higher in June to September than in the rest of the year.",
        "reasoning": (
            "A consistent seasonal pattern can be planned for: stockpiles, drainage and haul-road maintenance, "
            "and a monsoon-specific plan can be set before the season starts."
        ),
        "suggested_actions": [
            "Set the June to September plan from observed weather-delay hours rather than the annual average.",
            "Schedule haul-road drainage and stockpile builds before June.",
            "Use rainfall forecasts to trigger a weather protocol early (for example, standby "
            "crews and shift changes).",
        ],
        "evidence": [
            _evidence(
                "Mean weather delay, June to September",
                _round(float(monsoon["weather_delay_h"].mean()), 2),
                "h per zone-day",
                "all history",
            ),
            _evidence(
                "Mean weather delay, other months",
                _round(float(dry["weather_delay_h"].mean()), 2),
                "h per zone-day",
                "all history",
            ),
            _evidence("Ratio", _round(ratio, 2), "x", "all history", "estimate"),
        ],
        "expected_impact": {
            "status": "not_estimated",
            "value_t": None,
            "unit": "t",
            "basis": "No mitigation option is modelled, so no tonnage impact is estimated.",
        },
        "confidence": _confidence(True, len(scoped)),
        "limitations": ["Weather delay is recorded by the operation. Rainfall is treated as context only."],
    }
    return RuleResult(rule_id, title, True, recommendation["summary"], recommendation, checks)


def rule_blasting_pattern(rows: pd.DataFrame, as_of: date) -> RuleResult:
    rule_id, title = "blasting_delay", "Blasting delays"
    window, start = _window(rows, as_of, 90)
    scoped = window[window["blasting_delay_h"].notna()]
    period = f"{start.isoformat()} to {as_of.isoformat()}"
    if len(scoped) < 20:
        return RuleResult(rule_id, title, False, "Not enough blasting records in the last 90 days.")
    mean_hours = float(scoped["blasting_delay_h"].mean())
    checks = [{"mean_blasting_h_per_zone_day": _round(mean_hours, 2), "records": len(scoped)}]
    if mean_hours < policy.BLASTING_MEAN_H_PER_DAY:
        return RuleResult(
            rule_id,
            title,
            False,
            f"Mean blasting delay is {mean_hours:.2f} h per zone-day, below the "
            f"{policy.BLASTING_MEAN_H_PER_DAY:g} h trigger.",
            checks=checks,
        )
    by_weekday = scoped.assign(weekday=scoped["date"].dt.day_name()).groupby("weekday")["blasting_delay_h"].mean()
    worst_day = str(by_weekday.idxmax())
    recommendation: dict[str, Any] = {
        "id": "REC-BLAST-DELAY",
        "title": "Reduce blasting delays and review the blast schedule",
        "priority": "medium" if mean_hours < 2 * policy.BLASTING_MEAN_H_PER_DAY else "high",
        "category": "drilling_blasting",
        "zone_id": None,
        "summary": f"Blasting delays average {mean_hours:.2f} hours per zone-day, most often on {worst_day}s.",
        "reasoning": "Blasting delays stop loading and haulage, and they recur on the same "
        "weekday, which suggests a scheduling or clearance issue.",
        "suggested_actions": [
            f"Review the blast schedule for {worst_day}s and check clearance and re-blast procedures.",
            "Log a cause code for each blasting delay (misfire, clearance, drill availability, permit).",
        ],
        "evidence": [
            _evidence("Mean blasting delay", _round(mean_hours, 2), "h per zone-day", period),
            _evidence("Weekday with the highest mean delay", worst_day, "day", period),
        ],
        "expected_impact": {
            "status": "not_estimated",
            "value_t": None,
            "unit": "t",
            "basis": "The dataset has no cause codes, so the tonnage effect of each fix cannot be estimated.",
        },
        "confidence": _confidence(True, len(scoped)),
        "limitations": ["Blasting delay hours are as recorded; cause codes are not available."],
    }
    return RuleResult(rule_id, title, True, recommendation["summary"], recommendation, checks)


def rule_zone_concentration(rows: pd.DataFrame, as_of: date) -> RuleResult:
    rule_id, title = "zone_concentration", "Shortfall concentrated in one zone"
    window, start = _window(rows, as_of, policy.RECENT_WINDOW_DAYS)
    matched = window[window["actual_production_t"].notna()].copy()
    period = f"{start.isoformat()} to {as_of.isoformat()}"
    if matched["zone_id"].nunique() < 2:
        return RuleResult(rule_id, title, False, "Only one zone is in scope, so there is nothing to concentrate.")
    matched["gap"] = matched["actual_production_t"] - matched["planned_production_t"]
    shortfall = matched[matched["gap"] < 0].groupby("zone_id")["gap"].sum()
    total = float(shortfall.sum())
    if total >= 0:
        return RuleResult(rule_id, title, False, "No zone has a net shortfall in the recent window.")
    share = (shortfall / total * 100.0).sort_values(ascending=False)
    top_zone = str(share.index[0])
    top_share = float(share.iloc[0])
    checks = [{"zone_id": str(z), "share_of_shortfall_pct": _round(float(v), 1)} for z, v in share.items()]
    if top_share < policy.ZONE_GAP_CONCENTRATION_PCT:
        return RuleResult(
            rule_id,
            title,
            False,
            f"The largest share of shortfall tonnes is {top_share:.0f}% (zone {top_zone}), below the "
            f"{policy.ZONE_GAP_CONCENTRATION_PCT:g}% trigger.",
            checks=checks,
        )
    recommendation: dict[str, Any] = {
        "id": f"REC-FOCUS-{top_zone}",
        "title": f"Focus the shortfall investigation on zone {top_zone}",
        "priority": "medium",
        "category": "production",
        "zone_id": top_zone,
        "summary": f"Zone {top_zone} accounts for {top_share:.0f}% of shortfall tonnes in the recent window.",
        "reasoning": "Concentrated shortfalls are usually fixed faster by working on one zone "
        "than by changing the whole plan.",
        "suggested_actions": [
            f"Start the plan-versus-actual review with zone {top_zone}.",
            "Check its constraint hours against the other zones.",
        ],
        "evidence": [
            _evidence("Share of shortfall tonnes", _round(top_share, 1), "%", period),
            _evidence("Shortfall tonnes in zone", _round(float(shortfall.loc[top_zone]), 0), "t", period),
            _evidence("Total shortfall tonnes", _round(total, 0), "t", period),
        ],
        "expected_impact": {
            "status": "not_estimated",
            "value_t": None,
            "unit": "t",
            "basis": "Focusing the review does not by itself create tonnage; impact depends on the causes found.",
        },
        "confidence": _confidence(True, len(matched)),
        "limitations": ["Shortfall shares describe where gaps occurred, not why."],
    }
    return RuleResult(rule_id, title, True, recommendation["summary"], recommendation, checks)


def rule_data_completeness(rows: pd.DataFrame, as_of: date) -> RuleResult:
    rule_id, title = "data_completeness", "Missing actuals"
    window, start = _window(rows, as_of, policy.RECENT_WINDOW_DAYS)
    period = f"{start.isoformat()} to {as_of.isoformat()}"
    if window.empty:
        return RuleResult(rule_id, title, False, "No rows in the recent window.")
    coverage = float(window["actual_production_t"].notna().mean() * 100.0)
    checks = [{"coverage_pct": _round(coverage, 1), "rows": len(window)}]
    if coverage >= policy.DATA_COMPLETENESS_MIN_PCT:
        return RuleResult(
            rule_id,
            title,
            False,
            f"{coverage:.1f}% of rows in the recent window have actuals, meeting the "
            f"{policy.DATA_COMPLETENESS_MIN_PCT:g}% floor.",
            checks=checks,
        )
    missing = int(window["actual_production_t"].isna().sum())
    recommendation: dict[str, Any] = {
        "id": "REC-DATA-CAPTURE",
        "title": "Close gaps in production data capture",
        "priority": "medium",
        "category": "data",
        "zone_id": None,
        "summary": f"Only {coverage:.1f}% of recent rows have an actual value; {missing} rows are pending.",
        "reasoning": "Gaps in recording make plan-versus-actual comparisons unreliable and "
        "reduce the data available for forecasting.",
        "suggested_actions": [
            "Identify which zones and dates have no actuals and why (system outage, late entry, missing shift report).",
            "Agree a daily close-out deadline for production records.",
        ],
        "evidence": [
            _evidence("Rows with an actual value", _round(coverage, 1), "%", period),
            _evidence("Pending rows", missing, "rows", period),
        ],
        "expected_impact": {
            "status": "not_estimated",
            "value_t": None,
            "unit": "t",
            "basis": "Data capture does not change tonnage by itself.",
        },
        "confidence": _confidence(True, len(window)),
        "limitations": ["Pending rows are excluded from gap figures and from model training. No values were imputed."],
    }
    return RuleResult(rule_id, title, True, recommendation["summary"], recommendation, checks)


def rule_forecast_gap(risk: dict[str, Any] | None) -> RuleResult:
    rule_id, title = "forecast_gap", "Forecast shortfall over the next horizon"
    if risk is None or risk.get("expected") is None:
        return RuleResult(rule_id, title, False, "No forecast was available to test.")
    expected = risk["expected"]
    band = risk["band"]["level"]
    net = expected["net_gap_t"]
    horizon = risk["horizon"]
    days = horizon["forecast_days"]
    period = f"{horizon['start']} to {horizon['end']}"
    checks = [{"band": band, "net_gap_t": net, "net_gap_pct": expected["net_gap_pct"]}]
    if band not in {"high", "medium"} or net >= 0 or days == 0:
        return RuleResult(
            rule_id,
            title,
            False,
            f"Expected net gap over the next {days} days is {band} risk ({expected['net_gap_pct']}% of plan).",
            checks=checks,
        )
    uplift = abs(net) / days
    plan_daily = expected["plan_t"] / days
    uplift_pct = uplift / plan_daily * 100.0 if plan_daily else None
    recommendation: dict[str, Any] = {
        "id": "REC-FORECAST-RECOVERY",
        "title": "Prepare a recovery plan for the forecast shortfall",
        "priority": "high" if band == "high" else "medium",
        "category": "planning",
        "zone_id": None,
        "summary": (
            f"The forecast is {abs(expected['net_gap_pct'] or 0):.1f}% below plan over the next {days} days "
            f"({band.upper()} risk band)."
        ),
        "reasoning": (
            "The forecast gap is what the operation should expect if current conditions continue. A recovery plan "
            "shows how much daily uplift the plan would need."
        ),
        "suggested_actions": [
            "Decide whether the plan or the operating assumptions should change before the period starts.",
            f"Identify up to {abs(net):,.0f} t of recoverable output across zones (about {uplift:,.0f} t per day).",
            "Re-run the forecast after each week of actuals to check whether the gap is closing.",
        ],
        "evidence": [
            _evidence("Forecast output", expected["forecast_t"], "t", period, "forecast"),
            _evidence("Planned tonnes", expected["plan_t"], "t", period),
            _evidence("Expected net gap", net, "t", period, "estimate"),
            _evidence("Risk band", band, "level", period, "rule_based"),
        ],
        "expected_impact": {
            "status": "estimated",
            "value_t": _round(abs(net), 0),
            "unit": "t",
            "basis": (
                f"Arithmetic on the forecast: the net gap over {days} days divided by {days} days gives an uplift of "
                f"{uplift:,.0f} t per day"
                + (f" ({uplift_pct:.1f}% of average daily plan)." if uplift_pct is not None else ".")
                + " This is the size of the gap, not a forecast of what an action would recover."
            ),
        },
        "confidence": _confidence(True, days),
        "limitations": [
            "The forecast assumes operational inputs stay at their trailing averages.",
            "The interval is empirical from backtest windows; see the risk page.",
        ],
    }
    return RuleResult(rule_id, title, True, recommendation["summary"], recommendation, checks)


def rule_model_governance(risk: dict[str, Any] | None) -> RuleResult:
    rule_id, title = "model_governance", "Forecast reliability"
    if risk is None or risk.get("model_check") is None:
        return RuleResult(rule_id, title, False, "No forecast was available to test.")
    model_check = risk["model_check"]
    check = risk.get("classification_check") or {}
    regression_verdict = model_check["regression_verdict"]
    classifier_verdict = model_check["classifier_verdict"]
    checks = [
        {
            "regression_verdict": regression_verdict,
            "classifier_verdict": classifier_verdict,
            "brier_skill_pct": check.get("brier_skill_pct"),
        }
    ]
    weak_regression = regression_verdict != "beats_best_baseline"
    weak_classifier = classifier_verdict == "no_skill_over_base_rate"
    if not weak_regression and not weak_classifier:
        return RuleResult(
            rule_id,
            title,
            False,
            "The forecast beats the best baseline on the backtest, and the classifier adds skill over the base rate.",
            checks=checks,
        )
    if weak_regression:
        summary = "The ML forecast does not demonstrably beat the best simple baseline on the backtest."
    else:
        summary = "The daily shortfall classifier adds no reliable skill over the base rate on the backtest."
    recommendation: dict[str, Any] = {
        "id": "REC-MODEL-RELIABILITY",
        "title": "Treat the ML forecast as provisional",
        "priority": "medium",
        "category": "model",
        "zone_id": None,
        "summary": summary,
        "reasoning": "A forecast that cannot beat a simple baseline on past data should not "
        "drive decisions on its own.",
        "suggested_actions": [
            "Use the baseline comparison alongside the forecast when planning.",
            "Collect more history or additional drivers (geology, fleet availability) before relying on the model.",
        ],
        "evidence": [
            _evidence("Regression verdict", regression_verdict, "text", "backtest", "rule_based"),
            _evidence("Classifier verdict", classifier_verdict, "text", "backtest", "rule_based"),
            _evidence("Classifier Brier skill", check.get("brier_skill_pct"), "%", "backtest", "estimate"),
        ],
        "expected_impact": {
            "status": "not_estimated",
            "value_t": None,
            "unit": "t",
            "basis": "Model reliability does not change output by itself.",
        },
        "confidence": _confidence(True, int(check.get("n") or 0)),
        "limitations": ["Backtest results describe past periods only."],
    }
    return RuleResult(rule_id, title, True, summary, recommendation, checks)


def _confidence(has_core_evidence: bool, sample: int) -> dict[str, Any]:
    level = "medium" if has_core_evidence and sample >= 60 else "low"
    return {
        "level": level,
        "reasons": [
            f"{sample} records informed this rule.",
            "Rule thresholds are policy choices, not learned parameters.",
        ],
    }


# ----------------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------------
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def build_recommendations(
    frame: pd.DataFrame,
    scope: Scope,
    *,
    today: date,
    stale_days: int,
    risk: dict[str, Any] | None,
) -> dict[str, Any]:
    """Evaluate every rule for ``scope``.

    Windows are anchored on the scope's latest recorded actual (the data's own "as of" date).
    Freshness compares that date with ``today``.
    """
    rows = scope_rows(frame, scope)
    results: list[RuleResult] = []
    if rows.empty:
        return {"recommendations": [], "rules": [], "as_of": None, "notes": ["No rows in scope."]}

    last_actual = rows.loc[rows["actual_production_t"].notna(), "date"]
    if last_actual.empty:
        return {
            "recommendations": [],
            "rules": [],
            "as_of": None,
            "notes": ["No recorded actuals in this scope, so no rule can be evaluated."],
        }
    # Windows end on the last day with any recorded value, so a stretch of missing actuals is seen
    # by the completeness rule rather than hidden by moving the window earlier.
    operational = [c for c in ("equipment_downtime_h", "weather_delay_h", "blasting_delay_h") if c in rows]
    has_record = rows["actual_production_t"].notna()
    for column in operational:
        has_record = has_record | rows[column].notna()
    as_of = rows.loc[has_record, "date"].max().date()
    days_since = (today - last_actual.max().date()).days
    if days_since > stale_days:
        results.append(
            RuleResult(
                "data_freshness",
                "Stale data",
                True,
                f"The latest actual is {days_since} days old.",
                {
                    "id": "REC-DATA-FRESHNESS",
                    "title": "Refresh production data before relying on these figures",
                    "priority": "medium",
                    "category": "data",
                    "zone_id": None,
                    "summary": f"The latest recorded actual is {days_since} days before the as-of date.",
                    "reasoning": "Recommendations describe the period in the data. Old data may not "
                    "describe current operations.",
                    "suggested_actions": ["Upload the latest production records and re-check these recommendations."],
                    "evidence": [_evidence("Days since last actual", days_since, "days", f"as of {today.isoformat()}")],
                    "expected_impact": {
                        "status": "not_estimated",
                        "value_t": None,
                        "unit": "t",
                        "basis": "Not applicable.",
                    },
                    "confidence": _confidence(True, len(rows)),
                    "limitations": [],
                },
            )
        )
    else:
        results.append(RuleResult("data_freshness", "Stale data", False, "Data freshness is within the threshold."))

    results.extend(
        [
            rule_equipment_recurrence(rows, as_of),
            rule_production_deviation(rows, as_of),
            rule_monsoon_weather(rows, as_of),
            rule_blasting_pattern(rows, as_of),
            rule_zone_concentration(rows, as_of),
            rule_data_completeness(rows, as_of),
            rule_forecast_gap(risk),
            rule_model_governance(risk),
        ]
    )

    recommendations = [r.recommendation for r in results if r.fired and r.recommendation is not None]
    for item in recommendations:
        item["value_kind"] = "rule_based"
    recommendations.sort(key=lambda item: (PRIORITY_ORDER[item["priority"]], item["category"], item["id"]))
    rules = [
        {"rule_id": r.rule_id, "title": r.title, "fired": r.fired, "reason": r.reason, "checks": r.checks}
        for r in results
    ]
    notes = [
        "Each recommendation cites the evidence that triggered it. Rules with no trigger are "
        "listed under rules checked.",
        "Expected impacts marked 'estimated' are arithmetic on the data and are not causal effects.",
    ]
    if risk is None:
        notes.append("Forecast-based rules were not evaluated because no forecast was requested.")
    return {
        "as_of": as_of.isoformat(),
        "recommendations": recommendations,
        "rules": rules,
        "notes": notes,
        "window_days": policy.RECENT_WINDOW_DAYS,
    }


__all__ = ["build_recommendations"]
