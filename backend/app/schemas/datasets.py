"""Dataset registry models (stored manifests and API responses)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.provenance import SourceType
from app.schemas.common import Provenance, ValidationReport

DatasetKind = Literal["production", "drillholes", "exploration_zones"]


class DatasetManifest(BaseModel):
    """Persisted metadata for one dataset (``manifest.json``)."""

    model_config = ConfigDict(use_enum_values=True)

    id: str
    kind: DatasetKind
    name: str
    description: str = ""
    schema_version: str
    source_type: SourceType
    provenance: Provenance
    created_at: datetime
    row_count: int = 0
    date_min: date | None = None
    date_max: date | None = None
    mines: list[str] = Field(default_factory=list)
    zones: list[str] = Field(default_factory=list)
    rows_with_actual: int = 0
    rows_pending_actual: int = 0
    validation_status: Literal["valid", "valid_with_warnings", "invalid"] | None = None
    validation: ValidationReport | None = None
    data_file: str
    sha256: str
    size_bytes: int
    original_filename: str | None = None
    generator: dict[str, Any] | None = None


class DatasetSummary(BaseModel):
    id: str
    kind: DatasetKind
    name: str
    description: str
    source_type: SourceType
    source_label: str
    is_synthetic: bool
    deletable: bool
    created_at: datetime
    row_count: int
    date_min: date | None
    date_max: date | None
    mines: list[str]
    zones: list[str]
    rows_with_actual: int
    rows_pending_actual: int
    validation_status: str | None
    sha256: str


class DatasetList(BaseModel):
    datasets: list[DatasetSummary]


class DatasetDetail(DatasetSummary):
    provenance: Provenance
    validation: ValidationReport | None
    original_filename: str | None
    size_bytes: int
    generator: dict[str, Any] | None


class PreviewColumn(BaseModel):
    name: str
    unit: str | None = None


class DatasetPreview(BaseModel):
    dataset_id: str
    total_rows: int
    returned_rows: int
    columns: list[str]
    rows: list[dict[str, Any]]


class ProductionColumnDoc(BaseModel):
    name: str
    required: bool
    type: str
    unit: str
    description: str
    min_value: float | None = None
    max_value: float | None = None


class ProductionSchema(BaseModel):
    schema_version: str
    columns: list[ProductionColumnDoc]
    max_upload_mb: float
    max_upload_rows: int
    accepted_extensions: list[str]
    example_csv: str
