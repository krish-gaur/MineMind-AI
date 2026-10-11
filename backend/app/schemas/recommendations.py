"""Response models for recommendations."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.forecast import DatasetContext, ScopeInfo


class EvidenceItem(BaseModel):
    metric: str
    value: Any
    unit: str
    period: str
    value_kind: str


class ExpectedImpact(BaseModel):
    status: Literal["estimated", "not_estimated"]
    value_t: float | None
    unit: str
    basis: str


class Confidence(BaseModel):
    level: Literal["low", "medium"]
    reasons: list[str]


class RecommendationItem(BaseModel):
    id: str
    title: str
    priority: Literal["high", "medium", "low"]
    category: str
    zone_id: str | None
    summary: str
    reasoning: str
    suggested_actions: list[str]
    evidence: list[EvidenceItem]
    expected_impact: ExpectedImpact
    confidence: Confidence
    limitations: list[str]
    value_kind: Literal["rule_based"] = "rule_based"


class RuleOutcome(BaseModel):
    rule_id: str
    title: str
    fired: bool
    reason: str
    checks: list[dict[str, Any]] = Field(default_factory=list)


class RecommendationsResponse(BaseModel):
    dataset: DatasetContext
    scope: ScopeInfo
    as_of: str | None
    window_days: int
    recommendations: list[RecommendationItem]
    rules: list[RuleOutcome]
    notes: list[str]
