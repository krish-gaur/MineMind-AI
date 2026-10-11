"""Metadata endpoints: data-source registry and service capabilities."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings
from app.config import Settings
from app.domain.sources import list_sources

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/sources", summary="Data sources, licences and limitations")
def sources() -> dict[str, list[dict[str, Any]]]:
    return {"sources": list_sources()}


@router.get("/capabilities", summary="Which optional capabilities are enabled")
def capabilities(settings: Settings = Depends(get_app_settings)) -> dict[str, Any]:
    return {
        "external_services_enabled": settings.enable_external_services,
        "forecast_horizon_days": settings.forecast_horizon_days,
        "max_upload_mb": settings.max_upload_mb,
        "max_upload_rows": settings.max_upload_rows,
        "stale_data_days": settings.stale_data_days,
    }
