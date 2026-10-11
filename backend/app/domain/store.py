"""File-based dataset registry.

Each dataset lives in ``<DATA_DIR>/datasets/<id>/`` as ``manifest.json`` plus the
normalised data file. The directory name is always a validated identifier, so
user-supplied filenames never influence filesystem paths.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from app.domain.provenance import SourceType
from app.domain.schema import PRODUCTION_SCHEMA_VERSION
from app.domain.validation import ValidationOutcome
from app.errors import ForbiddenError, NotFoundError
from app.logging_config import get_logger
from app.schemas.datasets import DatasetManifest

log = get_logger("minemind.store")

DATASET_ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{2,63}$")
MANIFEST_NAME = "manifest.json"
PRODUCTION_FILE = "data.csv"
ZONES_FILE = "zones.geojson"
DRILLHOLES_FILE = "drillholes.csv"


def new_dataset_id(prefix: str = "upl") -> str:
    return f"{prefix}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{os.urandom(3).hex()}"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class DatasetStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.datasets_dir = self.root / "datasets"
        self._lock = threading.RLock()
        self._frame_cache: dict[str, tuple[float, pd.DataFrame]] = {}

    # ----- paths ---------------------------------------------------------
    def ensure_dirs(self) -> None:
        self.datasets_dir.mkdir(parents=True, exist_ok=True)

    def _dataset_dir(self, dataset_id: str) -> Path:
        if not DATASET_ID_RE.match(dataset_id):
            raise NotFoundError(f"Dataset '{dataset_id}' does not exist.")
        return self.datasets_dir / dataset_id

    def is_writable(self) -> bool:
        try:
            self.ensure_dirs()
            probe = self.datasets_dir / f".probe-{os.getpid()}"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True
        except OSError:
            return False

    # ----- reads ---------------------------------------------------------
    def list_manifests(self, kind: str | None = None) -> list[DatasetManifest]:
        self.ensure_dirs()
        manifests: list[DatasetManifest] = []
        for child in sorted(self.datasets_dir.iterdir()):
            if not child.is_dir() or not DATASET_ID_RE.match(child.name):
                continue
            manifest_path = child / MANIFEST_NAME
            if not manifest_path.exists():
                continue
            try:
                manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                log.warning(
                    "skipping unreadable manifest",
                    extra={"dataset_id": child.name, "event": "manifest_unreadable"},
                )
                continue
            if kind is None or manifest.kind == kind:
                manifests.append(manifest)
        manifests.sort(key=lambda m: (m.source_type != SourceType.SYNTHETIC, m.created_at), reverse=False)
        return manifests

    def get_manifest(self, dataset_id: str) -> DatasetManifest:
        path = self._dataset_dir(dataset_id) / MANIFEST_NAME
        if not path.exists():
            raise NotFoundError(f"Dataset '{dataset_id}' does not exist.")
        return DatasetManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def data_path(self, dataset_id: str) -> Path:
        manifest = self.get_manifest(dataset_id)
        return self._dataset_dir(dataset_id) / manifest.data_file

    def load_production(self, dataset_id: str) -> pd.DataFrame:
        """Return the normalised production table (cached by file mtime)."""
        path = self.data_path(dataset_id)
        mtime = path.stat().st_mtime
        with self._lock:
            cached = self._frame_cache.get(dataset_id)
            if cached and cached[0] == mtime:
                return cached[1].copy()
            frame = pd.read_csv(
                path,
                dtype={"mine_id": str, "zone_id": str},
                parse_dates=["date"],
            )
            self._frame_cache[dataset_id] = (mtime, frame)
            return frame.copy()

    # ----- writes --------------------------------------------------------
    def save_production(
        self,
        *,
        dataset_id: str,
        manifest_fields: dict[str, object],
        outcome: ValidationOutcome,
        csv_bytes: bytes,
    ) -> DatasetManifest:
        """Persist a validated production dataset atomically."""
        if outcome.frame is None:
            raise ValueError("Only validated datasets can be saved.")
        manifest = DatasetManifest(
            id=dataset_id,
            kind="production",
            schema_version=PRODUCTION_SCHEMA_VERSION,
            row_count=len(outcome.frame),
            date_min=outcome.report.date_min,
            date_max=outcome.report.date_max,
            mines=outcome.report.mines,
            zones=outcome.report.zones,
            mine_zones={
                str(mine): sorted(str(z) for z in group["zone_id"].unique())
                for mine, group in outcome.frame.groupby("mine_id")
            },
            rows_with_actual=outcome.report.rows_with_actual,
            rows_pending_actual=outcome.report.rows_pending_actual,
            validation_status=outcome.report.status,
            validation=outcome.report,
            data_file=PRODUCTION_FILE,
            sha256=sha256_hex(csv_bytes),
            size_bytes=len(csv_bytes),
            **manifest_fields,  # type: ignore[arg-type]
        )
        with self._lock:
            target = self._dataset_dir(dataset_id)
            staging = target.with_name(target.name + ".tmp")
            if staging.exists():
                shutil.rmtree(staging)
            staging.mkdir(parents=True)
            (staging / PRODUCTION_FILE).write_bytes(csv_bytes)
            (staging / MANIFEST_NAME).write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
            if target.exists():
                shutil.rmtree(target)
            os.replace(staging, target)
            self._frame_cache.pop(dataset_id, None)
        log.info(
            "dataset saved",
            extra={"dataset_id": dataset_id, "event": "dataset_saved", "source": manifest.source_type},
        )
        return manifest

    def read_bytes(self, dataset_id: str) -> bytes:
        return self.data_path(dataset_id).read_bytes()

    def save_artifact(
        self,
        *,
        manifest: DatasetManifest,
        payload: bytes,
    ) -> DatasetManifest:
        """Persist a non-production dataset (GeoJSON zones or drillhole CSV) atomically."""
        with self._lock:
            target = self._dataset_dir(manifest.id)
            staging = target.with_name(target.name + ".tmp")
            if staging.exists():
                shutil.rmtree(staging)
            staging.mkdir(parents=True)
            (staging / manifest.data_file).write_bytes(payload)
            (staging / MANIFEST_NAME).write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
            if target.exists():
                shutil.rmtree(target)
            os.replace(staging, target)
            self._frame_cache.pop(manifest.id, None)
        log.info(
            "dataset saved",
            extra={"dataset_id": manifest.id, "event": "dataset_saved", "source": manifest.source_type},
        )
        return manifest

    def delete(self, dataset_id: str) -> None:
        manifest = self.get_manifest(dataset_id)
        if manifest.source_type == SourceType.SYNTHETIC:
            raise ForbiddenError("Synthetic demonstration datasets cannot be deleted.")
        with self._lock:
            shutil.rmtree(self._dataset_dir(dataset_id), ignore_errors=False)
            self._frame_cache.pop(dataset_id, None)
        log.info("dataset deleted", extra={"dataset_id": dataset_id, "event": "dataset_deleted"})

    def has_dataset(self, dataset_id: str) -> bool:
        try:
            return (self._dataset_dir(dataset_id) / MANIFEST_NAME).exists()
        except NotFoundError:
            return False
