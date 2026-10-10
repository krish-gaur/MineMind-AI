"""Command-line helpers.

Examples (run from the backend folder)::

    python -m app.cli generate-demo
    python -m app.cli train --dataset demo-synthetic-production-v1
    python -m app.cli train --dataset demo-synthetic-production-v1 --all-scopes
    python -m app.cli status
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from app.config import get_settings
from app.domain.features import Scope
from app.domain.forecast_service import ForecastService
from app.domain.ingest import ensure_demo_dataset
from app.domain.store import DatasetStore
from app.domain.synthetic import DEMO_DATASET_ID
from app.errors import AppError


def _store() -> DatasetStore:
    settings = get_settings()
    store = DatasetStore(settings.data_dir)
    store.ensure_dirs()
    return store


def _scopes_for(store: DatasetStore, dataset_id: str) -> list[Scope]:
    manifest = store.get_manifest(dataset_id)
    frame = store.load_production(dataset_id)
    scopes = [Scope()]
    scopes += [Scope(mine_id=mine) for mine in manifest.mines]
    pairs = frame[["mine_id", "zone_id"]].drop_duplicates().sort_values(["mine_id", "zone_id"])
    scopes += [Scope(mine_id=row.mine_id, zone_id=row.zone_id) for row in pairs.itertuples(index=False)]
    return scopes


def cmd_generate_demo(_: argparse.Namespace) -> int:
    settings = get_settings()
    store = _store()
    manifest = ensure_demo_dataset(store)
    print(f"Synthetic demonstration dataset ready: {manifest.id} ({manifest.row_count} rows) in {settings.data_dir}")
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    settings = get_settings()
    store = _store()
    dataset_id = args.dataset or DEMO_DATASET_ID
    if dataset_id == DEMO_DATASET_ID:
        ensure_demo_dataset(store)
    service = ForecastService(store, settings.artifacts_dir, horizon_days=settings.forecast_horizon_days)
    scopes = _scopes_for(store, dataset_id) if args.all_scopes else [Scope(mine_id=args.mine, zone_id=args.zone)]
    failures = 0
    for scope in scopes:
        started = time.perf_counter()
        try:
            model, _series, source = service.model_for(dataset_id, scope)
        except AppError as exc:
            failures += 1
            print(f"[skip] {scope.label}: {exc.message}")
            continue
        elapsed = time.perf_counter() - started
        verdict = model.metrics["verdict"]
        print(f"[{source}] {scope.label}: verdict={verdict} labelled_days={model.labelled_days} ({elapsed:.1f}s)")
    return 1 if failures and failures == len(scopes) else 0


def cmd_status(_: argparse.Namespace) -> int:
    settings = get_settings()
    store = _store()
    print(f"data_dir: {Path(settings.data_dir).resolve()}")
    for manifest in store.list_manifests():
        print(f"- {manifest.id} [{manifest.source_type}] rows={manifest.row_count} status={manifest.validation_status}")
    models = Path(settings.artifacts_dir) / "models"
    saved = sorted(models.rglob("*.joblib")) if models.exists() else []
    print(f"saved models: {len(saved)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="MineMind AI maintenance commands.")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("generate-demo", help="Create the synthetic demonstration dataset.")
    demo.set_defaults(func=cmd_generate_demo)
    train = sub.add_parser("train", help="Train and save forecasting models.")
    train.add_argument("--dataset", help="Production dataset id (default: synthetic demo).")
    train.add_argument("--mine", help="Mine id for a single scope.")
    train.add_argument("--zone", help="Zone id for a single scope.")
    train.add_argument("--all-scopes", action="store_true", help="Train all mines and zones plus the overall scope.")
    train.set_defaults(func=cmd_train)
    sub.add_parser("status", help="List datasets and saved models.").set_defaults(func=cmd_status)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
