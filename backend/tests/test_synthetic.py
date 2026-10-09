"""Synthetic demonstration data: determinism, shape, and labelling guarantees."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pandas as pd

from app.domain.ingest import demo_provenance, ensure_demo_dataset
from app.domain.provenance import SourceType
from app.domain.store import DatasetStore
from app.domain.synthetic import (
    DEMO_DATASET_ID,
    HISTORY_END,
    MINE_NAMES,
    OUTPUT_COLUMNS,
    PENDING_DAYS,
    SERIES,
    frame_to_csv_bytes,
    generate_production_frame,
)
from app.domain.validation import validate_production_csv


def test_generator_is_deterministic_byte_for_byte() -> None:
    first = frame_to_csv_bytes(generate_production_frame())
    second = frame_to_csv_bytes(generate_production_frame())
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()


def test_generator_shape_and_identifiers_are_synthetic() -> None:
    frame = generate_production_frame()
    assert list(frame.columns) == OUTPUT_COLUMNS
    assert set(frame["mine_id"]) == set(MINE_NAMES)
    assert frame["mine_id"].str.startswith("SYN-").all()
    assert frame["zone_id"].str.startswith("SYN-").all()
    assert frame.groupby(["mine_id", "zone_id"]).ngroups == len(SERIES)


def test_plan_is_present_everywhere_and_pending_days_have_no_actuals() -> None:
    frame = generate_production_frame()
    assert frame["planned_production_t"].notna().all()
    pending = frame[frame["date"] > pd.Timestamp(HISTORY_END)]
    assert pending["date"].nunique() == PENDING_DAYS
    assert pending["actual_production_t"].isna().all()
    assert pending["equipment_downtime_h"].isna().all()


def test_recorded_gaps_exist_and_are_not_zero_filled() -> None:
    frame = generate_production_frame()
    history = frame[frame["date"] <= pd.Timestamp(HISTORY_END)]
    assert history["actual_production_t"].isna().any()
    assert (history["actual_production_t"].dropna() >= 0).all()
    assert not (history["actual_production_t"] == 0).any()


def test_generated_csv_passes_the_production_validator() -> None:
    csv_bytes = frame_to_csv_bytes(generate_production_frame())
    outcome = validate_production_csv(csv_bytes, max_rows=100_000, now=datetime(2026, 10, 9, tzinfo=UTC))
    assert outcome.report.status == "valid_with_warnings"
    assert outcome.frame is not None
    codes = {issue.code for issue in outcome.report.issues}
    assert "pending_actuals" in codes


def test_demo_provenance_is_labelled_synthetic_with_limitations() -> None:
    provenance = demo_provenance(datetime(2026, 10, 9, tzinfo=UTC))
    assert provenance.source_type == SourceType.SYNTHETIC
    assert "SYNTHETIC" in provenance.label
    assert any("Not MOIL operational data" in item for item in provenance.limitations)


def test_demo_manifest_is_synthetic_and_not_deletable(settings) -> None:  # type: ignore[no-untyped-def]
    store = DatasetStore(settings.data_dir)
    manifest = ensure_demo_dataset(store, now=datetime(2026, 10, 9, tzinfo=UTC))
    assert manifest.id == DEMO_DATASET_ID
    assert manifest.source_type == SourceType.SYNTHETIC
    assert "SYNTHETIC" in manifest.provenance.label
    assert manifest.generator is not None and manifest.generator["seed"] == 26009
    assert (
        "Not calibrated" in manifest.generator["calibration"]
        or "not calibrated" in manifest.generator["calibration"].lower()
    )
