"""Validation for GeoJSON exploration zones and drillhole CSV uploads.

Zones: a FeatureCollection of Polygon or MultiPolygon features in WGS84 (EPSG:4326 lon/lat). Each
feature needs a unique ``zone_id``. ``name`` and ``host_unit_mapped`` (true/false) are optional.
Drillholes: CSV with ``hole_id, zone_id, lon, lat, depth_m, mn_pct``. Grades must be 0-60 % Mn.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from shapely.geometry import shape
from shapely.validation import explain_validity

from app.errors import ValidationFailedError

MAX_GEOJSON_FEATURES = 500
MAX_DRILLHOLES = 20_000
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,39}$")
DRILLHOLE_COLUMNS = ("hole_id", "zone_id", "lon", "lat", "depth_m", "mn_pct")
MN_RANGE = (0.0, 60.0)
DEPTH_RANGE = (0.0, 2000.0)


@dataclass
class GeoValidation:
    status: str
    issues: list[str] = field(default_factory=list)
    count: int = 0


def _ring_inside_lonlat(coords: Any) -> bool:
    if not isinstance(coords, list):
        return False
    for ring in coords:
        for point in ring if ring and isinstance(ring[0], list) else []:
            if not isinstance(point, list) or len(point) < 2:
                return False
            lon, lat = point[0], point[1]
            if not (isinstance(lon, (int, float)) and isinstance(lat, (int, float))):
                return False
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                return False
    return True


def validate_zones_geojson(
    raw: bytes, *, max_features: int = MAX_GEOJSON_FEATURES
) -> tuple[dict[str, Any], GeoValidation]:
    """Return a cleaned FeatureCollection and its validation summary, or raise ValidationFailedError."""
    try:
        document = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationFailedError("The file is not valid UTF-8 JSON GeoJSON.") from exc
    if not isinstance(document, dict) or document.get("type") != "FeatureCollection":
        raise ValidationFailedError("GeoJSON must be a FeatureCollection.")
    features = document.get("features")
    if not isinstance(features, list) or not features:
        raise ValidationFailedError("The FeatureCollection has no features.")
    if len(features) > max_features:
        raise ValidationFailedError(f"The file has {len(features)} features; the limit is {max_features}.")

    issues: list[str] = []
    seen: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    for index, feature in enumerate(features, start=1):
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            issues.append(f"feature {index}: not a GeoJSON Feature")
            continue
        geometry = feature.get("geometry") or {}
        gtype = geometry.get("type")
        if gtype not in {"Polygon", "MultiPolygon"}:
            issues.append(f"feature {index}: geometry must be Polygon or MultiPolygon, found {gtype!r}")
            continue
        if not _ring_inside_lonlat(geometry.get("coordinates")):
            issues.append(f"feature {index}: coordinates must be [longitude, latitude] within -180..180 and -90..90")
            continue
        try:
            geom = shape(geometry)
        except (ValueError, TypeError) as exc:
            issues.append(f"feature {index}: geometry could not be read ({exc.__class__.__name__})")
            continue
        if not geom.is_valid:
            issues.append(f"feature {index}: invalid geometry ({explain_validity(geom)})")
            continue
        props = feature.get("properties") or {}
        zone_id = str(props.get("zone_id", "")).strip()
        if not ID_RE.match(zone_id):
            issues.append(f"feature {index}: zone_id is missing or has invalid characters")
            continue
        if zone_id in seen:
            issues.append(f"feature {index}: duplicate zone_id {zone_id!r}")
            continue
        seen.add(zone_id)
        host = props.get("host_unit_mapped")
        cleaned.append(
            {
                "type": "Feature",
                "properties": {
                    "zone_id": zone_id,
                    "name": str(props.get("name") or zone_id)[:80],
                    "host_unit_mapped": host if isinstance(host, bool) else None,
                    "is_synthetic": False,
                },
                "geometry": geometry,
            }
        )
    if not cleaned:
        raise ValidationFailedError("No valid zone features were found.", details={"issues": issues[:50]})
    status = "valid_with_warnings" if issues else "valid"
    return {"type": "FeatureCollection", "features": cleaned}, GeoValidation(status, issues[:50], len(cleaned))


def validate_drillholes_csv(raw: bytes, *, max_rows: int = MAX_DRILLHOLES) -> tuple[pd.DataFrame, GeoValidation]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationFailedError("The file is not UTF-8 encoded CSV.") from exc
    reader = csv.reader(io.StringIO(text, newline=""))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if len(rows) < 2:
        raise ValidationFailedError("The drillhole file needs a header and at least one row.")
    header = [cell.strip().lower() for cell in rows[0]]
    missing = [column for column in DRILLHOLE_COLUMNS if column not in header]
    if missing:
        raise ValidationFailedError(
            "Required column(s) missing: " + ", ".join(missing) + ". Found: " + ", ".join(header) + "."
        )
    body = rows[1:]
    if len(body) > max_rows:
        raise ValidationFailedError(f"The file has {len(body):,} rows; the limit is {max_rows:,}.")
    frame = pd.DataFrame([dict(zip(header, row, strict=False)) for row in body])
    issues: list[str] = []
    numeric: dict[str, pd.Series] = {}
    for column, (low, high) in {
        "lon": (-180, 180),
        "lat": (-90, 90),
        "depth_m": DEPTH_RANGE,
        "mn_pct": MN_RANGE,
    }.items():
        values = pd.to_numeric(frame[column].str.strip(), errors="coerce")
        bad = values.isna() & frame[column].str.strip().ne("")
        for index in frame.index[bad.to_numpy()][:20]:
            issues.append(f"line {index + 2}: {column} '{frame.at[index, column]}' is not a number")
        out_of_range = values.notna() & ((values < low) | (values > high))
        for index in frame.index[out_of_range.to_numpy()][:20]:
            issues.append(f"line {index + 2}: {column} must be between {low:g} and {high:g}")
        numeric[column] = values
    if issues:
        raise ValidationFailedError("Some drillhole rows are not valid.", details={"issues": issues[:50]})
    out = pd.DataFrame(
        {
            "hole_id": frame["hole_id"].str.strip(),
            "zone_id": frame["zone_id"].str.strip(),
            "lon": numeric["lon"],
            "lat": numeric["lat"],
            "depth_m": numeric["depth_m"],
            "mn_pct": numeric["mn_pct"],
        }
    )
    if out["hole_id"].eq("").any() or out["zone_id"].eq("").any():
        raise ValidationFailedError("hole_id and zone_id must not be blank.")
    duplicates = out["hole_id"].duplicated(keep=False)
    if duplicates.any():
        raise ValidationFailedError(
            "hole_id values must be unique.",
            details={"duplicates": sorted(out.loc[duplicates, "hole_id"].unique())[:20]},
        )
    if out["mn_pct"].isna().any():
        issues.append(
            f"{int(out['mn_pct'].isna().sum())} hole(s) have no Mn grade and are excluded from grade statistics"
        )
    status = "valid_with_warnings" if issues else "valid"
    return out.reset_index(drop=True), GeoValidation(status, issues[:50], len(out))
