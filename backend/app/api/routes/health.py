"""Liveness and readiness endpoints (used by Render health checks)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Response

from app import __version__
from app.api.deps import get_app_settings, get_store
from app.config import Settings
from app.domain.store import DatasetStore
from app.domain.synthetic import DEMO_DATASET_ID
from app.schemas.common import HealthResponse, ReadinessCheck, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health(settings: Settings = Depends(get_app_settings)) -> HealthResponse:
    """Process is up. Does not touch dependencies."""
    return HealthResponse(
        status="ok",
        version=__version__,
        environment=settings.app_env,
        time=datetime.now(UTC),
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    responses={503: {"model": ReadinessResponse}},
)
def ready(
    response: Response,
    store: DatasetStore = Depends(get_store),
    settings: Settings = Depends(get_app_settings),
) -> ReadinessResponse:
    """Storage is writable and the demonstration dataset is registered.

    External public services are reported but never make the service unready:
    the dashboard falls back to labelled offline data when they are unreachable.
    """
    checks: list[ReadinessCheck] = []
    writable = store.is_writable()
    checks.append(
        ReadinessCheck(
            name="storage",
            status="ok" if writable else "failed",
            detail="Data directory is writable." if writable else "Data directory is not writable.",
        )
    )
    demo_ready = store.has_dataset(DEMO_DATASET_ID)
    checks.append(
        ReadinessCheck(
            name="demo_dataset",
            status="ok" if demo_ready else "degraded",
            detail="Synthetic demonstration dataset is registered."
            if demo_ready
            else "Synthetic demonstration dataset is missing; it is generated at startup.",
        )
    )
    checks.append(
        ReadinessCheck(
            name="external_services",
            status="ok" if settings.enable_external_services else "degraded",
            detail="Public satellite and weather services are enabled."
            if settings.enable_external_services
            else "Public services disabled by configuration; offline fallbacks are used.",
        )
    )
    status: Literal["ready", "degraded", "not_ready"]
    if not writable:
        status = "not_ready"
        response.status_code = 503
    elif not demo_ready:
        status = "degraded"
    else:
        status = "ready"
    return ReadinessResponse(status=status, checks=checks)
