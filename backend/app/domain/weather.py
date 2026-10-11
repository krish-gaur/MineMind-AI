"""Daily precipitation at a point from the Open-Meteo historical archive (ERA5-based, CC BY 4.0)."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.domain.external import PublicJsonClient, ServiceResult

SERVICE_NAME = "Open-Meteo historical weather archive"


def daily_precipitation(
    client: PublicJsonClient,
    *,
    archive_url: str,
    lat: float,
    lon: float,
    start: date,
    end: date,
) -> tuple[ServiceResult, list[dict[str, Any]]]:
    params = {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "precipitation_sum",
        "timezone": "UTC",
    }
    cache_key = f"openmeteo|{archive_url}|{sorted(params.items())}"
    result = client.get_json(archive_url, params, cache_key=cache_key, service=SERVICE_NAME)
    if not result.ok:
        return result, []
    return result, parse_daily(result.data)


def parse_daily(payload: Any) -> list[dict[str, Any]]:
    """Return ``[{date, precipitation_mm}]``. Missing values stay ``None``; they are not zero-filled."""
    if not isinstance(payload, dict) or not isinstance(payload.get("daily"), dict):
        return []
    daily = payload["daily"]
    times = daily.get("time") or []
    values = daily.get("precipitation_sum") or []
    rows: list[dict[str, Any]] = []
    for day, value in zip(times, values, strict=False):
        number = float(value) if isinstance(value, (int, float)) else None
        rows.append({"date": str(day), "precipitation_mm": None if number is None else round(number, 1)})
    return rows
