"""Shortfall risk bands.

The band is a **rule-based** label applied to a forecast quantity: the expected net gap to plan
over the horizon. It is not a learned classifier. The daily shortfall classifier is reported
separately, with its own calibration and skill numbers, and does not set the band.
"""

from __future__ import annotations

from typing import Any

from app.domain import policy

BAND_LABELS: dict[str, str] = {
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "insufficient_data": "Not assessed",
}


def band_rule_text() -> str:
    return (
        f"HIGH when the expected net gap to plan is at or below -{policy.RISK_HIGH_SHORTFALL_PCT:g}%; "
        f"MEDIUM when it is at or below -{policy.RISK_MEDIUM_SHORTFALL_PCT:g}%; otherwise LOW. "
        "Thresholds are policy choices and are not learned from data."
    )


def classify_band(net_gap_pct: float | None) -> dict[str, Any]:
    if net_gap_pct is None:
        level = "insufficient_data"
    elif net_gap_pct <= -policy.RISK_HIGH_SHORTFALL_PCT:
        level = "high"
    elif net_gap_pct <= -policy.RISK_MEDIUM_SHORTFALL_PCT:
        level = "medium"
    else:
        level = "low"
    return {
        "level": level,
        "label": BAND_LABELS[level],
        "rule": band_rule_text(),
        "thresholds": {
            "high_at_or_below_pct": -policy.RISK_HIGH_SHORTFALL_PCT,
            "medium_at_or_below_pct": -policy.RISK_MEDIUM_SHORTFALL_PCT,
        },
        "expected_net_gap_pct": None if net_gap_pct is None else round(net_gap_pct, 2),
        "value_kind": "rule_based",
    }


def classification_verdict(classification: dict[str, Any]) -> tuple[str, str]:
    """Describe whether the daily shortfall classifier beats the base rate on the backtest."""
    skill = classification.get("brier_skill_pct")
    auc = classification.get("roc_auc")
    if auc is None:
        return (
            "not_evaluable",
            "Not evaluable on this backtest: the test window contains only one outcome class, so AUC is undefined.",
        )
    if skill is not None and skill > 0:
        return (
            "beats_base_rate",
            f"AUC {auc:.2f} and Brier skill {skill:+.1f}% against a base-rate forecast on the backtest.",
        )
    return (
        "no_skill_over_base_rate",
        f"AUC {auc:.2f} but Brier skill {skill:+.1f}% against the base rate: the classifier adds no reliable skill.",
    )
