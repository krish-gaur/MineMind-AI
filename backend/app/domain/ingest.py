"""Dataset ingestion: synthetic demo generation and validated uploads."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import PurePosixPath, PureWindowsPath

from app.domain.provenance import SourceType, source_label
from app.domain.store import DatasetStore, new_dataset_id
from app.domain.synthetic import (
    DEMO_DATASET_ID,
    GENERATOR_VERSION,
    frame_to_csv_bytes,
    generate_production_frame,
    generator_metadata,
)
from app.domain.validation import ProductionFileError, validate_production_csv
from app.errors import UnsupportedMediaError, ValidationFailedError
from app.logging_config import get_logger
from app.schemas.common import Provenance
from app.schemas.datasets import DatasetManifest

log = get_logger("minemind.ingest")

ALLOWED_PRODUCTION_EXTENSIONS = (".csv",)
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
        log.info(
            "regenerating demo dataset", extra={"dataset_id": DEMO_DATASET_ID, "event": "demo_regenerate"}
        )

    frame = generate_production_frame()
    csv_bytes = frame_to_csv_bytes(frame)
    from app.domain.validation import validate_production_csv as _validate

    outcome = _validate(csv_bytes, max_rows=max(len(frame), 1) + 1, now=now)
    if outcome.frame is None:
        raise RuntimeError("Synthetic generator produced an invalid dataset; this is a defect.")
    manifest_fields: dict[str, object] = {
        "name": "Synthetic demonstration production (SYN-A, SYN-B, SYN-C)",
        "description": (
            "SYNTHETIC. Fictional mines and zones for demonstrating the workflow. "
            "Not MOIL operational records."
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
