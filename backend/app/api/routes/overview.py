"""Executive overview endpoint (all figures computed from the selected dataset)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_app_settings, get_store
from app.config import Settings
from app.domain.kpis import ProductionFilter, compute_overview
from app.domain.provenance import SOURCE_LABELS, SourceType
from app.domain.store import DatasetStore
from app.domain.synthetic import DEMO_DATASET_ID
from app.errors import AppError, ValidationFailedError
from app.schemas.common import Provenance
from app.schemas.overview import (
    ConstraintItem,
    DatasetRef,
    FilterEcho,
    Freshness,
    Kpis,
    MonthlyPoint,
    OverviewResponse,
    PeriodInfo,
    ZoneSummary,
)

router = APIRouter(tags=["overview"])

SYNTHETIC_BANNER = (
    "SYNTHETIC DEMONSTRATION DATA - not MOIL operational records. Figures show how the workflow "
    "behaves; they are not evidence of real production performance."
)


def _validate_filters(
    manifest_mines: list[str], manifest_zones: list[str], mine_id: str | None, zone_id: str | None
) -> None:
    if mine_id and mine_id not in manifest_mines:
        raise ValidationFailedError(
            f"Mine '{mine_id}' is not in this dataset.",
            details={"valid_mines": manifest_mines},
        )
    if zone_id and zone_id not in manifest_zones:
        raise ValidationFailedError(
            f"Zone '{zone_id}' is not in this dataset.",
            details={"valid_zones": manifest_zones},
        )


@router.get("/overview", response_model=OverviewResponse, summary="Executive overview KPIs and trends")
def overview(
    dataset_id: str | None = Query(default=None, description="Production dataset id. Defaults to the synthetic demo."),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    mine_id: str | None = Query(default=None, max_length=40),
    zone_id: str | None = Query(default=None, max_length=40),
    store: DatasetStore = Depends(get_store),
    settings: Settings = Depends(get_app_settings),
) -> OverviewResponse:
    ds_id = dataset_id or DEMO_DATASET_ID
    manifest = store.get_manifest(ds_id)
    if manifest.kind != "production":
        raise AppError(
            "The overview needs a production dataset.",
            status_code=422,
            code="wrong_dataset_kind",
        )
    if start and end and start > end:
        raise ValidationFailedError("start must be on or before end.")
    _validate_filters(manifest.mines, manifest.zones, mine_id, zone_id)

    frame = store.load_production(ds_id)
    flt = ProductionFilter(start=start, end=end, mine_id=mine_id, zone_id=zone_id)
    as_of = datetime.now(UTC).date()
    data = compute_overview(frame, flt, as_of=as_of, stale_days=settings.stale_data_days)

    source_type = SourceType(manifest.source_type)
    is_synthetic = source_type is SourceType.SYNTHETIC
    provenance: Provenance = manifest.provenance
    notes: list[str] = []
    if is_synthetic:
        notes.append(SYNTHETIC_BANNER)
    if manifest.rows_pending_actual:
        notes.append(
            f"{manifest.rows_pending_actual} row(s) have no recorded actual yet. They are excluded from gap "
            "and attainment figures; no values were imputed."
        )
    if data["empty"]:
        notes.append("No records match the selected filters. Widen the date range or clear the mine/zone filter.")
    notes.append("Gap and attainment compare plan and actual on the same days only (matched days).")

    return OverviewResponse(
        dataset=DatasetRef(
            id=manifest.id,
            name=manifest.name,
            source_type=source_type.value,
            source_label=SOURCE_LABELS[source_type],
            is_synthetic=is_synthetic,
            banner=SYNTHETIC_BANNER if is_synthetic else None,
        ),
        filters=FilterEcho(start=start, end=end, mine_id=mine_id, zone_id=zone_id),
        empty=data["empty"],
        period=PeriodInfo(**data["period"]),
        kpis=Kpis(**data["kpis"]),
        constraints=[ConstraintItem(**item) for item in data["constraints"]],
        monthly=[MonthlyPoint(**item) for item in data["monthly"]],
        zones=[ZoneSummary(**item) for item in data["zones"]],
        freshness=Freshness(**data["freshness"]),
        provenance=provenance,
        notes=notes,
    )


__all__ = ["AppError", "router"]
