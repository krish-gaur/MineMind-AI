"""Recommendations endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_app_settings, get_forecast_service, get_store
from app.api.routes.forecast import HorizonQuery, _production_manifest, _scope
from app.config import Settings
from app.domain.forecast_service import ForecastService, dataset_context
from app.domain.recommendations import build_recommendations
from app.domain.store import DatasetStore
from app.schemas.recommendations import RecommendationsResponse

router = APIRouter(tags=["recommendations"])


@router.get(
    "/recommendations",
    response_model=RecommendationsResponse,
    summary="Evidence-backed recommendations for a scope",
)
def recommendations(
    dataset_id: str | None = Query(default=None),
    mine_id: str | None = Query(default=None, max_length=40),
    zone_id: str | None = Query(default=None, max_length=40),
    include_forecast: bool = Query(default=True, description="Also evaluate the forecast-based rules."),
    horizon_days: int = HorizonQuery,
    store: DatasetStore = Depends(get_store),
    service: ForecastService = Depends(get_forecast_service),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, Any]:
    manifest = _production_manifest(store, dataset_id)
    scope = _scope(store, manifest.id, mine_id, zone_id)
    frame = store.load_production(manifest.id)
    risk: dict[str, Any] | None = None
    if include_forecast:
        risk = service.risk_payload(manifest.id, scope, horizon_days, dataset_context(manifest))
    from datetime import UTC, datetime

    result = build_recommendations(
        frame,
        scope,
        today=datetime.now(UTC).date(),
        stale_days=settings.stale_data_days,
        risk=risk,
    )
    return {
        "dataset": dataset_context(manifest),
        "scope": {"mine_id": scope.mine_id, "zone_id": scope.zone_id, "label": scope.label, "key": scope.key},
        "as_of": result["as_of"],
        "window_days": result.get("window_days", 28),
        "recommendations": result["recommendations"],
        "rules": result["rules"],
        "notes": result["notes"],
    }
