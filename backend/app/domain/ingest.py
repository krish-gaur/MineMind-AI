"""Dataset ingestion: synthetic demo generation and validated uploads."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal

import pandas as pd

from app.domain.geo_ingest import validate_drillholes_csv, validate_zones_geojson
from app.domain.provenance import SourceType, source_label
from app.domain.store import DRILLHOLES_FILE, ZONES_FILE, DatasetStore, new_dataset_id, sha256_hex
from app.domain.synthetic import (
    DEMO_DATASET_ID,
    GENERATOR_VERSION,
    frame_to_csv_bytes,
    generate_production_frame,
    generator_metadata,
)
from app.domain.synthetic_geo import (
    DEMO_DRILLHOLES_DATASET_ID,
    DEMO_ZONES_DATASET_ID,
    GEO_GENERATOR_VERSION,
    SEED,
    demo_drillholes,
    demo_zones_collection,
)
from app.domain.validation import ProductionFileError, validate_production_csv
from app.errors import UnsupportedMediaError, ValidationFailedError
from app.logging_config import get_logger
from app.schemas.common import Provenance
from app.schemas.datasets import DatasetManifest

log = get_logger("minemind.ingest")

ALLOWED_PRODUCTION_EXTENSIONS = (".csv",)
ValidationStatus = Literal["valid", "valid_with_warnings", "invalid"]
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9 ._\-]")
MAX_NAME_LENGTH = 80


def sanitise_filename(raw: str | None) -> str | None:
    """Keep only the base name and a conservative character set. Never used as a path."""
    if not raw:
        return None
    base = PureWindowsPath(PurePosixPath(raw.replace("\\", "/")).name).name
    cleaned = _SAFE_NAME_RE.sub("_", base).strip(" .")
    return cleaned[:MAX_NAME_LENGTH] or None


def _clean_text(value: str | None, fallback: str, limit: int = MAX_NAME_LENGTH) -> str:
    text = (value or "").strip()
    text = _SAFE_NAME_RE.sub("_", text)[:limit].strip()
    return text or fallback


def demo_provenance(now: datetime) -> Provenance:
    return Provenance(
        source_type=SourceType.SYNTHETIC,
        label=source_label(SourceType.SYNTHETIC),
        provider="MineMind AI synthetic generator",
        description=(
            "Deterministic daily production records for fictional mines SYN-A, SYN-B and SYN-C. "
            "Planned and actual tonnes, equipment downtime, weather and blasting delays, and rainfall "
            "are generated from simple, documented rules."
        ),
        url=None,
        licence="Not applicable (synthetic data generated for this demonstration).",
        attribution=None,
        timestamp=now,
        limitations=[
            "Not MOIL operational data and not calibrated to any real mine.",
            "Relationships between delays and output are designed into the generator; "
            "associations found in this dataset describe the generator, not real operations.",
            "Rainfall is synthetic here. Enrich the dataset with a public rainfall series to replace it.",
            "Last 30 days contain plan rows only (no actuals), mirroring a planning horizon.",
        ],
    )


def ensure_demo_dataset(store: DatasetStore, *, now: datetime | None = None) -> DatasetManifest:
    """Create (or refresh) the synthetic demonstration dataset. Idempotent and deterministic."""
    now = now or datetime.now(UTC)
    store.ensure_dirs()
    if store.has_dataset(DEMO_DATASET_ID):
        existing = store.get_manifest(DEMO_DATASET_ID)
        if existing.generator and existing.generator.get("generator") == GENERATOR_VERSION:
            return existing
        log.info("regenerating demo dataset", extra={"dataset_id": DEMO_DATASET_ID, "event": "demo_regenerate"})

    frame = generate_production_frame()
    csv_bytes = frame_to_csv_bytes(frame)
    from app.domain.validation import validate_production_csv as _validate

    outcome = _validate(csv_bytes, max_rows=max(len(frame), 1) + 1, now=now)
    if outcome.frame is None:
        raise RuntimeError("Synthetic generator produced an invalid dataset; this is a defect.")
    manifest_fields: dict[str, object] = {
        "name": "Synthetic demonstration production (SYN-A, SYN-B, SYN-C)",
        "description": (
            "SYNTHETIC. Fictional mines and zones for demonstrating the workflow. Not MOIL operational records."
        ),
        "source_type": SourceType.SYNTHETIC,
        "provenance": demo_provenance(now),
        "created_at": now,
        "original_filename": None,
        "generator": generator_metadata(),
    }
    manifest = store.save_production(
        dataset_id=DEMO_DATASET_ID, manifest_fields=manifest_fields, outcome=outcome, csv_bytes=csv_bytes
    )
    return manifest


def _status(value: str) -> ValidationStatus:
    if value == "invalid":
        return "invalid"
    return "valid_with_warnings" if value == "valid_with_warnings" else "valid"


def _user_provenance(now: datetime, description: str, limitations: list[str]) -> Provenance:
    return Provenance(
        source_type=SourceType.USER_PROVIDED,
        label=source_label(SourceType.USER_PROVIDED),
        provider="User upload",
        description=description,
        timestamp=now,
        limitations=limitations,
    )


def ingest_zones_upload(
    store: DatasetStore,
    *,
    raw: bytes,
    filename: str | None,
    name: str | None,
    description: str | None,
    now: datetime | None = None,
) -> DatasetManifest:
    """Validate a GeoJSON file of exploration zones and store it."""
    now = now or datetime.now(UTC)
    safe_name = sanitise_filename(filename)
    if safe_name is None or not safe_name.lower().endswith((".geojson", ".json")):
        raise UnsupportedMediaError("Upload a .geojson (or .json) FeatureCollection of exploration zones.")
    collection, report = validate_zones_geojson(raw)
    payload = json.dumps(collection, indent=2, sort_keys=True).encode("utf-8")
    dataset_id = new_dataset_id("zon")
    zone_ids = sorted(str(f["properties"]["zone_id"]) for f in collection["features"])
    manifest = DatasetManifest(
        id=dataset_id,
        kind="exploration_zones",
        name=_clean_text(name, safe_name.rsplit(".", 1)[0]),
        description=_clean_text(description, "User-provided exploration zones.", limit=280),
        schema_version="exploration_zones.v1",
        source_type=SourceType.USER_PROVIDED,
        provenance=_user_provenance(
            now,
            "Exploration zone polygons supplied by a user. Geometry is validated; geology is not verified.",
            [
                "Zone boundaries and host-unit flags are not verified by MineMind AI.",
                "Not a licence or legal boundary.",
            ],
        ),
        created_at=now,
        row_count=report.count,
        mines=[],
        zones=zone_ids,
        validation_status=_status(report.status),
        validation_notes=report.issues,
        data_file=ZONES_FILE,
        sha256=sha256_hex(payload),
        size_bytes=len(payload),
        original_filename=safe_name,
    )
    return store.save_artifact(manifest=manifest, payload=payload)


def ingest_drillholes_upload(
    store: DatasetStore,
    *,
    raw: bytes,
    filename: str | None,
    name: str | None,
    description: str | None,
    now: datetime | None = None,
) -> DatasetManifest:
    """Validate a drillhole CSV (collars and Mn grades) and store it."""
    now = now or datetime.now(UTC)
    safe_name = sanitise_filename(filename)
    if safe_name is None or not safe_name.lower().endswith(".csv"):
        raise UnsupportedMediaError("Upload a .csv file of drillhole collars and grades.")
    frame, report = validate_drillholes_csv(raw)
    payload = frame_to_drillhole_csv(frame)
    dataset_id = new_dataset_id("drl")
    manifest = DatasetManifest(
        id=dataset_id,
        kind="drillholes",
        name=_clean_text(name, safe_name.rsplit(".", 1)[0]),
        description=_clean_text(description, "User-provided drillhole results.", limit=280),
        schema_version="drillholes.v1",
        source_type=SourceType.USER_PROVIDED,
        provenance=_user_provenance(
            now,
            "Drillhole collars and Mn grades supplied by a user. Assay quality is not verified by MineMind AI.",
            [
                "Grades are not verified against assay certificates or QA/QC records.",
                "A drillhole summary is not a reserve or resource estimate.",
            ],
        ),
        created_at=now,
        row_count=report.count,
        mines=[],
        zones=sorted(frame["zone_id"].unique().tolist()),
        validation_status=_status(report.status),
        validation_notes=report.issues,
        data_file=DRILLHOLES_FILE,
        sha256=sha256_hex(payload),
        size_bytes=len(payload),
        original_filename=safe_name,
    )
    return store.save_artifact(manifest=manifest, payload=payload)


def frame_to_drillhole_csv(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, float_format="%.5f", na_rep="", lineterminator="\n").encode("utf-8")


def ensure_demo_exploration(
    store: DatasetStore, *, now: datetime | None = None
) -> tuple[DatasetManifest, DatasetManifest]:
    """Create the synthetic zones and drillhole datasets (idempotent, deterministic)."""
    now = now or datetime.now(UTC)
    store.ensure_dirs()
    existing_zones = store.get_manifest(DEMO_ZONES_DATASET_ID) if store.has_dataset(DEMO_ZONES_DATASET_ID) else None
    existing_holes = (
        store.get_manifest(DEMO_DRILLHOLES_DATASET_ID) if store.has_dataset(DEMO_DRILLHOLES_DATASET_ID) else None
    )
    if (
        existing_zones
        and existing_holes
        and existing_zones.generator
        and existing_zones.generator.get("generator") == GEO_GENERATOR_VERSION
    ):
        return existing_zones, existing_holes

    provenance = Provenance(
        source_type=SourceType.SYNTHETIC,
        label=source_label(SourceType.SYNTHETIC),
        provider="MineMind AI synthetic geology generator",
        description=(
            "Fictional zone polygons, host-unit flags and drillhole grades for demonstrating the prioritisation "
            "workflow. Invented values; not survey, assay or licence data."
        ),
        licence="Not applicable (synthetic).",
        timestamp=now,
        limitations=[
            "Not a real geological map, drillhole log, assay or boundary.",
            "Grades and host-unit flags are invented to exercise the scoring code.",
            "Rankings from this data demonstrate the method only; they are not exploration findings.",
        ],
    )
    collection = demo_zones_collection()
    zones_payload = json.dumps(collection, indent=2, sort_keys=True).encode("utf-8")
    zones_manifest = DatasetManifest(
        id=DEMO_ZONES_DATASET_ID,
        kind="exploration_zones",
        name="Synthetic demonstration exploration zones",
        description="SYNTHETIC. Six fictional zones in the demonstration area.",
        schema_version="exploration_zones.v1",
        source_type=SourceType.SYNTHETIC,
        provenance=provenance,
        created_at=now,
        row_count=len(collection["features"]),
        mines=[],
        zones=[f["properties"]["zone_id"] for f in collection["features"]],
        validation_status="valid",
        validation_notes=[],
        data_file=ZONES_FILE,
        sha256=sha256_hex(zones_payload),
        size_bytes=len(zones_payload),
        generator={"generator": GEO_GENERATOR_VERSION, "seed": SEED},
    )
    holes = demo_drillholes()
    holes_payload = frame_to_drillhole_csv(holes)
    holes_manifest = DatasetManifest(
        id=DEMO_DRILLHOLES_DATASET_ID,
        kind="drillholes",
        name="Synthetic demonstration drillholes",
        description="SYNTHETIC. Invented collars and Mn grades in the demonstration zones.",
        schema_version="drillholes.v1",
        source_type=SourceType.SYNTHETIC,
        provenance=provenance,
        created_at=now,
        row_count=len(holes),
        mines=[],
        zones=sorted(holes["zone_id"].unique().tolist()),
        validation_status="valid",
        validation_notes=[],
        data_file=DRILLHOLES_FILE,
        sha256=sha256_hex(holes_payload),
        size_bytes=len(holes_payload),
        generator={"generator": GEO_GENERATOR_VERSION, "seed": SEED},
    )
    store.save_artifact(manifest=zones_manifest, payload=zones_payload)
    store.save_artifact(manifest=holes_manifest, payload=holes_payload)
    return zones_manifest, holes_manifest


def ingest_production_upload(
    store: DatasetStore,
    *,
    raw: bytes,
    filename: str | None,
    name: str | None,
    description: str | None,
    max_rows: int,
    now: datetime | None = None,
) -> DatasetManifest:
    """Validate and store a user-provided production CSV, or raise ValidationFailedError."""
    now = now or datetime.now(UTC)
    safe_name = sanitise_filename(filename)
    if safe_name is None or not safe_name.lower().endswith(ALLOWED_PRODUCTION_EXTENSIONS):
        raise UnsupportedMediaError("Upload a .csv file for production records.")

    try:
        outcome = validate_production_csv(raw, max_rows=max_rows, now=now)
    except ProductionFileError as exc:
        raise ValidationFailedError(str(exc), details=None) from exc

    if outcome.frame is None:
        report = outcome.report.model_dump(mode="json")
        raise ValidationFailedError(
            "The dataset was not stored because it has validation errors. See details.",
            details=report,
        )

    dataset_id = new_dataset_id("usr")
    provenance = Provenance(
        source_type=SourceType.USER_PROVIDED,
        label=source_label(SourceType.USER_PROVIDED),
        provider="User upload",
        description=(
            "Production records supplied by a user. MineMind AI has validated the schema and "
            "ranges but cannot verify that the values are correct."
        ),
        timestamp=now,
        limitations=[
            "Source authenticity and measurement quality are not verified by MineMind AI.",
            "Results are only as reliable as the uploaded records.",
        ],
    )
    csv_bytes = frame_to_csv_bytes(outcome.frame)
    fields: dict[str, object] = {
        "name": _clean_text(name, safe_name.rsplit(".", 1)[0]),
        "description": _clean_text(description, "User-provided production records.", limit=280),
        "source_type": SourceType.USER_PROVIDED,
        "provenance": provenance,
        "created_at": now,
        "original_filename": safe_name,
        "generator": None,
    }
    manifest = store.save_production(
        dataset_id=dataset_id, manifest_fields=fields, outcome=outcome, csv_bytes=csv_bytes
    )
    log.info(
        "user dataset stored",
        extra={"dataset_id": dataset_id, "event": "upload_accepted", "source": "user_provided"},
    )
    return manifest
