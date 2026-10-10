"""Report generation endpoint (HTML or JSON download)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response

from app.api.deps import get_app_settings, get_forecast_service, get_store
from app.config import Settings
from app.domain.forecast_service import ForecastService
from app.domain.reports import build_report, render_html
from app.domain.store import DatasetStore
from app.schemas.reports import ReportRequest

router = APIRouter(prefix="/reports", tags=["reports"])
_SAFE = re.compile(r"[^A-Za-z0-9_.-]")


@router.post(
    "",
    summary="Generate a self-contained HTML or JSON report",
    responses={200: {"content": {"text/html": {}, "application/json": {}}}},
)
def generate_report(
    body: ReportRequest,
    store: DatasetStore = Depends(get_store),
    service: ForecastService = Depends(get_forecast_service),
    settings: Settings = Depends(get_app_settings),
) -> Response:
    report = build_report(
        store=store,
        service=service,
        dataset_id=body.dataset_id,
        mine_id=body.mine_id,
        zone_id=body.zone_id,
        start=body.start,
        end=body.end,
        horizon_days=body.horizon_days,
        sections=list(body.sections),
        title=body.title,
        stale_days=settings.stale_data_days,
        zones_dataset_id=body.zones_dataset_id,
        drillholes_dataset_id=body.drillholes_dataset_id,
    )
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    stem = _SAFE.sub("_", f"minemind-report-{report['dataset']['id']}-{stamp}")[:90]
    if body.format == "json":
        payload = json.dumps(report, indent=2, default=str).encode("utf-8")
        return Response(
            content=payload,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{stem}.json"'},
        )
    html_text = render_html(report).encode("utf-8")
    return Response(
        content=html_text,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{stem}.html"'},
    )
