"""Dataset registry, preview, validation and upload endpoints."""

from __future__ import annotations

import math
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.api.deps import get_app_settings, get_store
from app.config import Settings
from app.domain.ingest import ALLOWED_PRODUCTION_EXTENSIONS, ingest_production_upload
from app.domain.provenance import SOURCE_LABELS, SourceType
from app.domain.schema import PRODUCTION_COLUMNS
from app.domain.store import DatasetStore
from app.domain.synthetic import SEED, frame_to_csv_bytes
from app.errors import AppError, PayloadTooLargeError, ValidationFailedError
from app.schemas.datasets import (
    DatasetDetail,
    DatasetList,
    DatasetManifest,
    DatasetPreview,
    DatasetSummary,
    ProductionColumnDoc,
    ProductionSchema,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])

EXAMPLE_CSV = (
    "date,mine_id,zone_id,planned_production_t,actual_production_t,"
    "equipment_downtime_h,weather_delay_h,blasting_delay_h,rainfall_mm\n"
    "2026-09-01,SYN-A,SYN-A-Z1,1400.0,1287.5,2.5,0.0,0.0,0.0\n"
    "2026-09-01,SYN-A,SYN-A-Z2,900.0,,4.0,1.2,0.5,0.0\n"
)


def summary_of(manifest: DatasetManifest) -> DatasetSummary:
    return DatasetSummary(
        id=manifest.id,
        kind=manifest.kind,
        name=manifest.name,
        description=manifest.description,
        source_type=manifest.source_type,
        source_label=SOURCE_LABELS[SourceType(manifest.source_type)],
        is_synthetic=SourceType(manifest.source_type) is SourceType.SYNTHETIC,
        deletable=SourceType(manifest.source_type) is not SourceType.SYNTHETIC,
        created_at=manifest.created_at,
        row_count=manifest.row_count,
        date_min=manifest.date_min,
        date_max=manifest.date_max,
        mines=manifest.mines,
        zones=manifest.zones,
        rows_with_actual=manifest.rows_with_actual,
        rows_pending_actual=manifest.rows_pending_actual,
        validation_status=manifest.validation_status,
        sha256=manifest.sha256,
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return value


@router.get("/schema/production", response_model=ProductionSchema, summary="Production CSV contract")
def production_schema(settings: Settings = Depends(get_app_settings)) -> ProductionSchema:
    return ProductionSchema(
        schema_version="production.v1",
        columns=[
            ProductionColumnDoc(
                name=c.name,
                required=c.required,
                type=c.dtype,
                unit=c.unit,
                description=c.description,
                min_value=c.min_value,
                max_value=c.max_value,
            )
            for c in PRODUCTION_COLUMNS
        ],
        max_upload_mb=settings.max_upload_mb,
        max_upload_rows=settings.max_upload_rows,
        accepted_extensions=list(ALLOWED_PRODUCTION_EXTENSIONS),
        example_csv=EXAMPLE_CSV,
    )


@router.get("", response_model=DatasetList, summary="List registered datasets")
def list_datasets(
    kind: Annotated[Literal["production", "drillholes", "exploration_zones"] | None, Query()] = None,
    store: DatasetStore = Depends(get_store),
) -> DatasetList:
    return DatasetList(datasets=[summary_of(m) for m in store.list_manifests(kind)])


@router.get("/{dataset_id}", response_model=DatasetDetail, summary="Dataset metadata and validation report")
def get_dataset(dataset_id: str, store: DatasetStore = Depends(get_store)) -> DatasetDetail:
    manifest = store.get_manifest(dataset_id)
    base = summary_of(manifest).model_dump()
    return DatasetDetail(
        **base,
        provenance=manifest.provenance,
        validation=manifest.validation,
        original_filename=manifest.original_filename,
        size_bytes=manifest.size_bytes,
        generator=manifest.generator,
    )


@router.get("/{dataset_id}/preview", response_model=DatasetPreview, summary="First rows of a dataset")
def preview_dataset(
    dataset_id: str,
    rows: Annotated[int, Query(ge=1, le=200)] = 20,
    store: DatasetStore = Depends(get_store),
) -> DatasetPreview:
    frame = store.load_production(dataset_id)
    head = frame.head(rows).copy()
    head["date"] = head["date"].dt.strftime("%Y-%m-%d")
    records = [
        {column: _json_safe(value) for column, value in record.items()}
        for record in head.to_dict(orient="records")
    ]
    return DatasetPreview(
        dataset_id=dataset_id,
        total_rows=len(frame),
        returned_rows=len(records),
        columns=list(frame.columns),
        rows=records,
    )


@router.get(
    "/{dataset_id}/export",
    summary="Download the normalised dataset as CSV",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
def export_dataset(dataset_id: str, store: DatasetStore = Depends(get_store)) -> Response:
    frame = store.load_production(dataset_id)
    manifest = store.get_manifest(dataset_id)
    payload = frame_to_csv_bytes(frame)
    filename = f"{manifest.id}.csv"
    return Response(
        content=payload,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "",
    response_model=DatasetDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and validate a production CSV",
    responses={
        413: {"description": "File exceeds the upload limit."},
        415: {"description": "Only .csv files are accepted."},
        422: {"description": "Validation failed; the report is in error.details."},
    },
)
async def upload_dataset(
    file: Annotated[UploadFile, File(description="Production CSV (UTF-8, header row required).")],
    name: Annotated[str | None, Form(max_length=120)] = None,
    description: Annotated[str | None, Form(max_length=400)] = None,
    kind: Annotated[Literal["production"], Form()] = "production",
    store: DatasetStore = Depends(get_store),
    settings: Settings = Depends(get_app_settings),
) -> DatasetDetail:
    del kind  # only production uploads are supported in this release
    limit = settings.max_upload_bytes
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise PayloadTooLargeError(f"The file is larger than the {settings.max_upload_mb:g} MB upload limit.")
    try:
        manifest = ingest_production_upload(
            store,
            raw=raw,
            filename=file.filename,
            name=name,
            description=description,
            max_rows=settings.max_upload_rows,
        )
    except ValidationFailedError:
        raise
    except AppError:
        raise
    return DatasetDetail(
        **summary_of(manifest).model_dump(),
        provenance=manifest.provenance,
        validation=manifest.validation,
        original_filename=manifest.original_filename,
        size_bytes=manifest.size_bytes,
        generator=manifest.generator,
    )


@router.delete(
    "/{dataset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user-provided dataset",
    responses={403: {"description": "Synthetic demonstration data cannot be deleted."}},
)
def delete_dataset(dataset_id: str, store: DatasetStore = Depends(get_store)) -> Response:
    store.delete(dataset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["SEED", "router"]
