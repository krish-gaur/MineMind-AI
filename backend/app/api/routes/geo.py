"""Geospatial layers, satellite scene search and public rainfall."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import get_app_settings, get_store
from app.config import Settings
from app.domain import satellite, weather
from app.domain.external import PublicJsonClient
from app.domain.provenance import SourceType
from app.domain.store import DatasetStore
from app.domain.synthetic_geo import (
    AOI_BBOX,
    DEMO_ZONES_DATASET_ID,
    demo_aoi_feature,
    demo_mine_features,
)
from app.errors import AppError, ValidationFailedError
from app.schemas.datasets import DatasetManifest

router = APIRouter(prefix="/geo", tags=["geospatial"])
MAX_WINDOW_DAYS = 366


def get_public_client(request: Request) -> PublicJsonClient:
    client: PublicJsonClient = request.app.state.public
    return client


def _zones_manifest(store: DatasetStore, dataset_id: str | None) -> DatasetManifest:
    manifest = store.get_manifest(dataset_id or DEMO_ZONES_DATASET_ID)
    if manifest.kind != "exploration_zones":
        raise AppError("This dataset is not a set of exploration zones.", status_code=422, code="wrong_dataset_kind")
    return manifest


def _feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


@router.get("/layers", summary="Map layers and their provenance")
def layers(
    zones_dataset_id: str | None = Query(default=None),
    store: DatasetStore = Depends(get_store),
) -> dict[str, Any]:
    zones = _zones_manifest(store, zones_dataset_id)
    zone_source = SourceType(zones.source_type)
    return {
        "layers": [
            {
                "id": "aoi",
                "label": "Demonstration area",
                "feature_type": "aoi",
                "count": 1,
                "source_type": SourceType.SYNTHETIC.value,
                "is_synthetic": True,
                "note": "Illustrative rectangle. Not a licence or concession boundary.",
            },
            {
                "id": "mines",
                "label": "Mine outlines (synthetic)",
                "feature_type": "mine_boundary",
                "count": len(demo_mine_features()),
                "source_type": SourceType.SYNTHETIC.value,
                "is_synthetic": True,
                "note": "Fictional outlines for SYN-A, SYN-B and SYN-C. Not MOIL boundaries.",
            },
            {
                "id": "zones",
                "label": f"Exploration zones: {zones.name}",
                "feature_type": "exploration_zone",
                "count": zones.row_count,
                "dataset_id": zones.id,
                "source_type": zone_source.value,
                "is_synthetic": zone_source is SourceType.SYNTHETIC,
                "note": zones.provenance.description,
            },
        ],
        "aoi_bbox": list(AOI_BBOX),
        "attribution": {
            "basemap": "Natural Earth country outlines (public domain), bundled offline.",
            "optional_online_basemap": "Set NEXT_PUBLIC_MAP_STYLE_URL to use an online style. Check its attribution.",
        },
    }


@router.get("/layers/{layer_id}", summary="GeoJSON for one map layer")
def layer(
    layer_id: Literal["aoi", "mines", "zones"],
    dataset_id: str | None = Query(default=None),
    store: DatasetStore = Depends(get_store),
) -> dict[str, Any]:
    if layer_id == "aoi":
        return _feature_collection([demo_aoi_feature()])
    if layer_id == "mines":
        return _feature_collection(demo_mine_features())
    manifest = _zones_manifest(store, dataset_id)
    document = json.loads(store.read_bytes(manifest.id).decode("utf-8"))
    features = document.get("features", [])
    for feature in features:
        feature.setdefault("properties", {})["dataset_id"] = manifest.id
    return _feature_collection(features)


@router.get("/satellite/scenes", summary="Sentinel-2 L2A scenes over an area (metadata only)")
def scenes(
    request: Request,
    bbox: str = Query(
        default=",".join(str(v) for v in AOI_BBOX),
        description="minLon,minLat,maxLon,maxLat in WGS84.",
        max_length=80,
    ),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    max_cloud: float | None = Query(default=30.0, ge=0, le=100),
    limit: int = Query(default=20, ge=1, le=100),
    client: PublicJsonClient = Depends(get_public_client),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, Any]:
    del request
    box = _parse_bbox(bbox)
    end_day = end or datetime.now(UTC).date()
    start_day = start or (end_day - timedelta(days=90))
    _check_window(start_day, end_day)
    result, items = satellite.search_scenes(
        client,
        base_url=settings.cdse_stac_url,
        bbox=box,
        start=start_day,
        end=end_day,
        max_cloud=max_cloud,
        limit=limit,
    )
    return {
        "status": result.status,
        "message": result.message,
        "retrieved_at": result.retrieved_at.isoformat() if result.retrieved_at else None,
        "bbox": list(box),
        "start": start_day.isoformat(),
        "end": end_day.isoformat(),
        "max_cloud_pct": max_cloud,
        "scenes": items,
        "source": {
            "name": satellite.SERVICE_NAME,
            "licence": "Copernicus Sentinel data: free and open access.",
            "attribution": "Contains modified Copernicus Sentinel data [year].",
        },
        "value_kind": "measured",
    }


@router.get("/weather/daily", summary="Daily precipitation at a point (public reanalysis)")
def weather_daily(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    start: date = Query(),
    end: date = Query(),
    client: PublicJsonClient = Depends(get_public_client),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, Any]:
    _check_window(start, end)
    result, days = weather.daily_precipitation(
        client,
        archive_url=settings.open_meteo_archive_url,
        lat=lat,
        lon=lon,
        start=start,
        end=end,
    )
    total = round(sum(d["precipitation_mm"] or 0.0 for d in days), 1) if days else None
    return {
        "status": result.status,
        "message": result.message,
        "retrieved_at": result.retrieved_at.isoformat() if result.retrieved_at else None,
        "location": {"lat": lat, "lon": lon},
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": days,
        "total_precipitation_mm": total,
        "missing_days": sum(1 for d in days if d["precipitation_mm"] is None),
        "source": {
            "name": weather.SERVICE_NAME,
            "licence": "Open-Meteo data: CC BY 4.0. Commercial use needs a paid Open-Meteo plan.",
            "attribution": "Weather data by Open-Meteo.com (CC BY 4.0); ERA5 by Copernicus Climate Change Service.",
        },
        "value_kind": "measured",
    }


def _parse_bbox(text: str) -> tuple[float, float, float, float]:
    try:
        values = [float(part) for part in text.split(",")]
    except ValueError as exc:
        raise ValidationFailedError("bbox must be four numbers: minLon,minLat,maxLon,maxLat.") from exc
    if len(values) != 4:
        raise ValidationFailedError("bbox must be four numbers: minLon,minLat,maxLon,maxLat.")
    min_lon, min_lat, max_lon, max_lat = values
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise ValidationFailedError("bbox is out of range or not ordered (min must be below max).")
    return (min_lon, min_lat, max_lon, max_lat)


def _check_window(start: date, end: date) -> None:
    if start > end:
        raise ValidationFailedError("start must be on or before end.")
    if (end - start).days > MAX_WINDOW_DAYS:
        raise ValidationFailedError(f"The date window is limited to {MAX_WINDOW_DAYS} days.")
