"""Risk bands and classifier verdicts: boundaries, wording and rule-based labelling."""

from __future__ import annotations

import pytest

from app.domain import policy
from app.domain.risk import band_rule_text, classification_verdict, classify_band


@pytest.mark.parametrize(
    ("net_gap_pct", "level"),
    [
        (-12.0, "high"),
        (-5.0, "high"),  # boundary: at or below the high threshold
        (-4.99, "medium"),
        (-2.0, "medium"),  # boundary
        (-1.99, "low"),
        (0.0, "low"),
        (3.5, "low"),
        (None, "insufficient_data"),
    ],
)
def test_band_boundaries(net_gap_pct: float | None, level: str) -> None:
    assert classify_band(net_gap_pct)["level"] == level


def test_band_is_labelled_as_rule_based_with_thresholds() -> None:
    band = classify_band(-6.0)
    assert band["value_kind"] == "rule_based"
    assert band["thresholds"] == {
        "high_at_or_below_pct": -policy.RISK_HIGH_SHORTFALL_PCT,
        "medium_at_or_below_pct": -policy.RISK_MEDIUM_SHORTFALL_PCT,
    }
    assert "not learned" in band["rule"]
    assert "-5%" in band_rule_text()


def test_classifier_verdict_branches() -> None:
    assert classification_verdict({"roc_auc": None, "brier_skill_pct": None})[0] == "not_evaluable"
    assert classification_verdict({"roc_auc": 0.8, "brier_skill_pct": 6.0})[0] == "beats_base_rate"
    code, text = classification_verdict({"roc_auc": 0.45, "brier_skill_pct": -2.0})
    assert code == "no_skill_over_base_rate"
    assert "no reliable skill" in text
