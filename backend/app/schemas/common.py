"""Shared response models: provenance, validation reports and health checks."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.provenance import SourceType, ValueKind


class Provenance(BaseModel):
    """Where a dataset or observation came from, and how it may be used."""

    model_config = ConfigDict(use_enum_values=True)

    source_type: SourceType
    label: str
    provider: str
    description: str
    url: str | None = None
    licence: str | None = None
    attribution: str | None = None
    timestamp: datetime | None = Field(default=None, description="Generation, upload or retrieval time (UTC).")
    limitations: list[str] = Field(default_factory=list)


class ValueLabel(BaseModel):
    """Describes the kind of a reported value (measured, forecast, ...)."""

    model_config = ConfigDict(use_enum_values=True)

    kind: ValueKind
    label: str


class ValidationIssue(BaseModel):
    severity: Literal["error", "warning"]
    code: str
    message: str
    affected_rows: int = 0
    examples: list[str] = Field(default_factory=list)


class ColumnProfile(BaseModel):
    name: str
    present: bool
    required: bool
    unit: str
    missing_count: int = 0
    missing_pct: float | None = None
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    outlier_count: int = 0
    outlier_rule: str | None = None


class ValidationReport(BaseModel):
    status: Literal["valid", "valid_with_warnings", "invalid"]
    schema_version: str
    row_count: int
    issues: list[ValidationIssue] = Field(default_factory=list)
    columns: list[ColumnProfile] = Field(default_factory=list)
    unknown_columns: list[str] = Field(default_factory=list)
    date_min: date | None = None
    date_max: date | None = None
    series_count: int = 0
    mines: list[str] = Field(default_factory=list)
    zones: list[str] = Field(default_factory=list)
    rows_with_actual: int = 0
    rows_pending_actual: int = 0
    missing_date_gaps: int = 0
    generated_at: datetime


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    environment: str
    time: datetime


class ReadinessCheck(BaseModel):
    name: str
    status: Literal["ok", "degraded", "failed"]
    detail: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded", "not_ready"]
    checks: list[ReadinessCheck]
