"""Response models for the executive overview."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.domain.provenance import ValueKind
from app.schemas.common import Provenance


class DatasetRef(BaseModel):
    id: str
    name: str
    source_type: str
    source_label: str
    is_synthetic: bool
    banner: str | None = Field(
        default=None, description="Prominent caveat shown wherever this dataset's numbers appear."
    )


class FilterEcho(BaseModel):
    start: date | None
    end: date | None
    mine_id: str | None
    zone_id: str | None


class PeriodInfo(BaseModel):
    start: date | None
    end: date | None
    days: int
    rows: int
    rows_with_actual: int
    rows_pending_actual: int
    series: int


class Kpis(BaseModel):
    planned_t: float | None
    actual_t: float | None
    gap_t: float | None
    variance_pct: float | None
    attainment_pct: float | None
    coverage_pct: float | None
    days_below_plan_pct: float | None
    equipment_downtime_h_total: float | None
    equipment_downtime_h_per_zone_day: float | None
    equipment_downtime_days_over_threshold_pct: float | None
    value_kind: ValueKind = ValueKind.MEASURED


class ConstraintItem(BaseModel):
    key: str
    label: str
    column: str
    total_hours: float | None
    share_pct: float | None
    mean_hours_per_zone_day: float | None
    records: int
    threshold_hours: float
    days_over_threshold: int
    value_kind: ValueKind = ValueKind.MEASURED


class MonthlyPoint(BaseModel):
    month: str
    planned_t: float | None
    actual_t: float | None
    gap_t: float | None
    attainment_pct: float | None
    records_with_actual: int
    equipment_downtime_h_mean: float | None


class ZoneSummary(BaseModel):
    mine_id: str
    zone_id: str
    records: int
    pending_rows: int
    planned_t: float | None
    actual_t: float | None
    gap_t: float | None
    variance_pct: float | None
    attainment_pct: float | None
    equipment_downtime_h_total: float | None
    weather_delay_h_total: float | None
    blasting_delay_h_total: float | None


class Freshness(BaseModel):
    last_actual_date: date | None
    days_since_last_actual: int | None
    stale_threshold_days: int
    status: str
    as_of: date


class OverviewResponse(BaseModel):
    dataset: DatasetRef
    filters: FilterEcho
    empty: bool
    period: PeriodInfo
    kpis: Kpis
    constraints: list[ConstraintItem]
    monthly: list[MonthlyPoint]
    zones: list[ZoneSummary]
    freshness: Freshness
    provenance: Provenance
    notes: list[str]
