"""Sentinel-2 L2A scene search (Copernicus Data Space STAC). Metadata only; no imagery is processed."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.domain.external import PublicJsonClient, ServiceResult

SERVICE_NAME = "Copernicus Data Space STAC catalogue"
COLLECTION = "sentinel-2-l2a"


def search_scenes(
    client: PublicJsonClient,
    *,
    base_url: str,
    bbox: tuple[float, float, float, float],
    start: date,
    end: date,
    max_cloud: float | None,
    limit: int,
) -> tuple[ServiceResult, list[dict[str, Any]]]:
    params = {
        "collections": COLLECTION,
        "bbox": ",".join(f"{value:.5f}" for value in bbox),
        "datetime": f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z",
        "limit": str(min(max(limit, 1), 100)),
    }
    cache_key = f"stac|{base_url}|{sorted(params.items())}"
    result = client.get_json(f"{base_url.rstrip('/')}/search", params, cache_key=cache_key, service=SERVICE_NAME)
    if not result.ok:
        return result, []
    return result, normalise_scenes(result.data, max_cloud)


def normalise_scenes(payload: Any, max_cloud: float | None) -> list[dict[str, Any]]:
    """Keep the fields the UI needs and apply the cloud filter on the catalogue's own estimate."""
    if not isinstance(payload, dict):
        return []
    scenes: list[dict[str, Any]] = []
    for feature in payload.get("features", []) or []:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties") or {}
        cloud = props.get("eo:cloud_cover")
        cloud_value = float(cloud) if isinstance(cloud, (int, float)) else None
        if max_cloud is not None and cloud_value is not None and cloud_value > max_cloud:
            continue
        assets = feature.get("assets") or {}
        preview_href = None
        for key in ("thumbnail", "preview", "quicklook"):
            asset = assets.get(key) if isinstance(assets, dict) else None
            href = asset.get("href") if isinstance(asset, dict) else None
            if isinstance(href, str) and href.startswith("https://"):
                preview_href = href
                break
        scenes.append(
            {
                "id": str(feature.get("id", "")),
                "acquired": props.get("datetime"),
                "cloud_cover_pct": None if cloud_value is None else round(cloud_value, 1),
                "tile": props.get("s2:mgrs_tile"),
                "platform": props.get("platform"),
                "footprint": feature.get("geometry"),
                "preview_url": preview_href,
                "value_kind": "measured",
            }
        )
    scenes.sort(key=lambda item: str(item.get("acquired") or ""), reverse=True)
    return scenes
