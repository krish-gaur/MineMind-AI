"""Response models for forecasting, backtest evaluation and shortfall risk.

Value types are explicit on every block: ``forecast`` (regression output), ``probability``
(classifier or empirical share), ``estimate`` (arithmetic on forecasts), ``scenario``
(assumed operational inputs) and ``rule_based`` (policy thresholds).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import Provenance


class ScopeInfo(BaseModel):
    mine_id: str | None
    zone_id: str | None
    label: str
    key: str


class DatasetContext(BaseModel):
    id: str
    name: str
    source_type: str
    source_label: str
    is_synthetic: bool
    banner: str | None
    date_max: str | None
    provenance: Provenance


class ModelCard(BaseModel):
    name: str
    regressor: str
    classifier: str
    value_kind: Literal["forecast"] = "forecast"
    source: Literal["memory", "loaded", "trained"]
    model_version: str
    fingerprint: str
    trained_at: str
    trained_on: dict[str, Any]
    features: list[str]
    config: dict[str, int]
    versions: dict[str, str]
    random_state: int


class ModelMetric(BaseModel):
    name: str
    label: str
    kind: Literal["model", "baseline"]
    mae: float
    rmse: float
    n: int


class FoldInfo(BaseModel):
    fold: int
    train_end: str
    test_start: str
    test_end: str
    train_days: int
    test_days: int
    gradient_boosting_mae: float


class GapToBaseline(BaseModel):
    mae_difference: float = Field(
        description="Gradient boosting MAE minus best baseline MAE (t/day). Negative is better."
    )
    ci95_low: float
    ci95_high: float
    skill_pct_vs_best_baseline: float | None
    bootstrap: str


class Evaluation(BaseModel):
    method: str
    evaluation_start: str
    evaluation_end: str
    n_evaluated_days: int
    folds: list[FoldInfo]
    models: list[ModelMetric]
    per_fold: list[dict[str, Any]]
    mae_by_fold: dict[str, dict[str, float]]
    best_baseline: str
    gap_to_best_baseline: GapToBaseline
    verdict: str
    verdict_text: str
    residual_q10_t: float
    residual_q90_t: float
    model_labels: dict[str, str]


class Classification(BaseModel):
    target: str
    model: str
    n: int
    base_rate: float
    roc_auc: float | None
    brier: float
    brier_climatology: float
    brier_skill_pct: float | None
    calibration: list[dict[str, Any]]
    verdict: str
    verdict_text: str
    value_kind: Literal["probability"] = "probability"


class HistoryPoint(BaseModel):
    date: str
    actual_t: float | None
    plan_t: float | None
    gradient_boosting_t: float | None
    ridge_t: float | None
    seasonal_naive_7_t: float | None
    shortfall_probability: float | None


class ForecastDay(BaseModel):
    date: str
    plan_t: float
    forecast_t: float
    interval_low_t: float
    interval_high_t: float
    shortfall_probability: float


class ForecastTotals(BaseModel):
    plan_t: float
    forecast_t: float
    net_gap_t: float
    net_gap_pct: float | None
    gap_interval_low_t: float | None
    gap_interval_high_t: float | None
    interval_basis: str
    period_shortfall_probability: float | None
    mean_daily_shortfall_probability: float
    start: str
    end: str


class ForecastBlock(BaseModel):
    requested_days: int
    forecast_days: int
    truncated_reason: str | None
    scenario_assumptions: dict[str, Any]
    days: list[ForecastDay]
    totals: ForecastTotals | None = None


class Drivers(BaseModel):
    forecast_drivers: list[dict[str, Any]]
    forecast_drivers_method: str | None
    shortfall_coefficients: list[dict[str, Any]]
    shortfall_method: str


class ForecastResponse(BaseModel):
    dataset: DatasetContext
    scope: ScopeInfo
    model: ModelCard
    evaluation: Evaluation
    classification: Classification
    backtest_history: list[HistoryPoint]
    forecast: ForecastBlock
    drivers: Drivers
    value_kinds: dict[str, str]
    notes: list[str]


class ExpectedBlock(BaseModel):
    plan_t: float
    forecast_t: float
    net_gap_t: float
    net_gap_pct: float | None
    gap_interval_low_t: float | None
    gap_interval_high_t: float | None
    interval_basis: str
    value_kind: Literal["estimate"] = "estimate"
    forecast_value_kind: Literal["forecast"] = "forecast"


class ShortfallProbabilityBlock(BaseModel):
    period_probability: float | None
    period_basis: str
    mean_daily_probability: float
    daily_definition: str
    value_kind: Literal["probability"] = "probability"


class BandBlock(BaseModel):
    level: Literal["high", "medium", "low", "insufficient_data"]
    label: str
    rule: str
    thresholds: dict[str, float]
    expected_net_gap_pct: float | None
    value_kind: Literal["rule_based"] = "rule_based"


class ClassificationCheck(BaseModel):
    verdict: str
    text: str
    roc_auc: float | None
    brier_skill_pct: float | None
    base_rate: float
    n: int


class HorizonInfo(BaseModel):
    requested_days: int
    forecast_days: int
    start: str | None
    end: str | None


class ModelCheck(BaseModel):
    regression_verdict: str
    regression_text: str
    classifier_verdict: str


class RiskResponse(BaseModel):
    dataset: DatasetContext
    scope: ScopeInfo
    horizon: HorizonInfo
    expected: ExpectedBlock | None
    shortfall_probability: ShortfallProbabilityBlock | None
    band: BandBlock
    classification_check: ClassificationCheck | None
    model_check: ModelCheck | None
    drivers: list[dict[str, Any]]
    limitations: list[str]
    source: Literal["memory", "loaded", "trained"]
