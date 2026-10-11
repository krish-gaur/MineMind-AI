"""Forecast, backtest and shortfall-risk endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_app_settings, get_forecast_service, get_store
from app.config import Settings
from app.domain.features import Scope
from app.domain.forecast_service import ForecastService, dataset_context
from app.domain.store import DatasetStore
from app.domain.synthetic import DEMO_DATASET_ID
from app.errors import AppError, ValidationFailedError
from app.schemas.datasets import DatasetManifest
from app.schemas.forecast import ForecastResponse, RiskResponse

router = APIRouter(tags=["forecasting"])

HorizonQuery = Query(default=30, ge=7, le=90, description="Days after the last recorded actual.")


def _production_manifest(store: DatasetStore, dataset_id: str | None) -> DatasetManifest:
    manifest = store.get_manifest(dataset_id or DEMO_DATASET_ID)
    if manifest.kind != "production":
        raise AppError("Forecasting needs a production dataset.", status_code=422, code="wrong_dataset_kind")
    return manifest


def _scope(store: DatasetStore, dataset_id: str, mine_id: str | None, zone_id: str | None) -> Scope:
    manifest = store.get_manifest(dataset_id)
    if mine_id and mine_id not in manifest.mines:
        raise ValidationFailedError(
            f"Mine '{mine_id}' is not in this dataset.", details={"valid_mines": manifest.mines}
        )
    if zone_id and zone_id not in manifest.zones:
        raise ValidationFailedError(
            f"Zone '{zone_id}' is not in this dataset.", details={"valid_zones": manifest.zones}
        )
    if mine_id and zone_id:
        frame = store.load_production(dataset_id)
        if not ((frame["mine_id"] == mine_id) & (frame["zone_id"] == zone_id)).any():
            raise ValidationFailedError(
                f"Zone '{zone_id}' does not belong to mine '{mine_id}'.",
                details={"zones_in_mine": sorted(frame.loc[frame["mine_id"] == mine_id, "zone_id"].unique().tolist())},
            )
    return Scope(mine_id=mine_id or None, zone_id=zone_id or None)


@router.get(
    "/forecast",
    response_model=ForecastResponse,
    summary="Forecast, backtest evaluation and classification for a scope",
    responses={422: {"description": "Insufficient data, or invalid scope or horizon."}},
)
def forecast(
    dataset_id: str | None = Query(default=None),
    mine_id: str | None = Query(default=None, max_length=40),
    zone_id: str | None = Query(default=None, max_length=40),
    horizon_days: int = HorizonQuery,
    store: DatasetStore = Depends(get_store),
    service: ForecastService = Depends(get_forecast_service),
) -> dict[str, Any]:
    manifest = _production_manifest(store, dataset_id)
    scope = _scope(store, manifest.id, mine_id, zone_id)
    return service.forecast_payload(manifest.id, scope, horizon_days, dataset_context(manifest))


@router.get(
    "/risk",
    response_model=RiskResponse,
    summary="Expected shortfall and rule-based risk band for a scope",
    responses={422: {"description": "Insufficient data, or invalid scope or horizon."}},
)
def risk(
    dataset_id: str | None = Query(default=None),
    mine_id: str | None = Query(default=None, max_length=40),
    zone_id: str | None = Query(default=None, max_length=40),
    horizon_days: int = HorizonQuery,
    store: DatasetStore = Depends(get_store),
    service: ForecastService = Depends(get_forecast_service),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, Any]:
    del settings
    manifest = _production_manifest(store, dataset_id)
    scope = _scope(store, manifest.id, mine_id, zone_id)
    return service.risk_payload(manifest.id, scope, horizon_days, dataset_context(manifest))
