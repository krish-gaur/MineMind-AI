"""Exploration-zone prioritisation: an evidence-gated index, not a probability or reserve estimate.

Indicators (scored)
-------------------
* ``host_unit_mapped``  - the (user-supplied) geological map shows the host lithology in the zone (0 or 1).
* ``mean_mn_pct``        - mean manganese grade of drillholes in the zone (percent Mn).
* ``share_high_grade``   - share of drillhole intercepts at or above the cut-off grade (default 20% Mn).

Context only (not scored)
-------------------------
Vegetation, rainfall, soil-moisture or surface-temperature indices. These respond to many
non-mineral processes, so they are shown for context and never change the score.

Gating
------
A zone is ranked only when at least ``MIN_EVIDENCE_CLASSES_TO_RANK`` independent evidence classes
(geological map, drilling) are present, and at least ``MIN_ZONES_TO_RANK`` zones have comparable data
for normalisation. Otherwise the zone's indicators are shown without a rank.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd
from shapely.geometry import shape

from app.domain import policy

HIGH_GRADE_CUTOFF_PCT = 20.0
WEIGHTS: dict[str, float] = {"host_unit_mapped": 0.2, "mean_mn_pct": 0.4, "share_high_grade": 0.4}
INDICATOR_LABELS: dict[str, str] = {
    "host_unit_mapped": "Host unit mapped in zone (geological map)",
    "mean_mn_pct": "Mean drillhole Mn grade (%)",
    "share_high_grade": f"Share of intercepts at or above {HIGH_GRADE_CUTOFF_PCT:g}% Mn",
}
EVIDENCE_CLASS: dict[str, str] = {
    "host_unit_mapped": "geological_map",
    "mean_mn_pct": "drilling",
    "share_high_grade": "drilling",
}
REQUIRED_INPUTS: tuple[str, ...] = (
    "Geological map (lithology and structure) at a suitable scale, with the host unit mapped by a geologist.",
    "Drillhole collars, depths and assays (Mn %), with QA/QC records and sample intervals.",
    "Known occurrences and past mine records, to test proximity and to calibrate the index.",
    "Field observations of surface manganese mineralisation (float, outcrop), with coordinates.",
    "Terrain (DEM) and structural data, if slope or lineament indicators are to be considered.",
    "Validation by a competent geologist. Spatial cross-validation before any ranking is used for decisions.",
)


@dataclass
class ZoneInput:
    zone_id: str
    name: str
    area_km2: float | None
    host_unit_mapped: bool | None
    holes: pd.DataFrame


def polygon_area_km2(geometry: dict[str, Any]) -> float | None:
    """Approximate planar area on a local equirectangular projection (error well under 1% for small zones)."""
    try:
        geom = shape(geometry)
    except (ValueError, TypeError):
        return None
    if geom.is_empty:
        return None
    centroid = geom.centroid
    lat_rad = math.radians(centroid.y)
    km_per_deg_lat = 110.574
    km_per_deg_lon = 111.320 * math.cos(lat_rad)
    return round(geom.area * km_per_deg_lat * km_per_deg_lon, 3)


def _holes_in_zone(holes: pd.DataFrame, zone_id: str) -> pd.DataFrame:
    if holes.empty or "zone_id" not in holes:
        return holes.iloc[0:0]
    return holes[holes["zone_id"] == zone_id]


def _normalise(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    low, high = min(values.values()), max(values.values())
    if math.isclose(high, low):
        return {key: 1.0 for key in values}
    return {key: (value - low) / (high - low) for key, value in values.items()}


def score_zones(
    zones: list[ZoneInput],
    *,
    cutoff: float = HIGH_GRADE_CUTOFF_PCT,
) -> dict[str, Any]:
    """Compute indicators, status and (where gated) a rank for every zone."""
    per_zone: list[dict[str, Any]] = []
    raw_indicators: dict[str, dict[str, float]] = {name: {} for name in WEIGHTS}

    for zone in zones:
        holes = zone.holes
        grades = holes["mn_pct"].dropna() if "mn_pct" in holes else pd.Series(dtype=float)
        indicators: dict[str, float | None] = {
            "host_unit_mapped": (1.0 if zone.host_unit_mapped else 0.0) if zone.host_unit_mapped is not None else None,
            "mean_mn_pct": float(grades.mean()) if len(grades) else None,
            "share_high_grade": float((grades >= cutoff).mean()) if len(grades) else None,
        }
        for name, value in indicators.items():
            if value is not None:
                raw_indicators[name][zone.zone_id] = value
        if len(grades):
            status = "observed"
        elif zone.host_unit_mapped is not None:
            status = "inferred" if zone.host_unit_mapped else "host_unit_not_mapped"
        else:
            status = "unavailable"
        per_zone.append(
            {
                "zone_id": zone.zone_id,
                "name": zone.name,
                "area_km2": zone.area_km2,
                "status": status,
                "drillholes": len(holes),
                "indicators": indicators,
            }
        )

    normalised = {name: _normalise(values) for name, values in raw_indicators.items()}
    comparable_zones = {zid for values in raw_indicators.values() for zid in values}
    can_normalise = len(comparable_zones) >= policy.MIN_ZONES_TO_RANK

    scored: list[tuple[str, float]] = []
    for entry in per_zone:
        zid = entry["zone_id"]
        indicator_rows: list[dict[str, Any]] = []
        for name, label in INDICATOR_LABELS.items():
            value = entry["indicators"][name]
            present = value is not None
            norm = normalised[name].get(zid) if present else None
            indicator_rows.append(
                {
                    "indicator": name,
                    "label": label,
                    "value": None if value is None else round(value, 3),
                    "normalised": None if norm is None else round(norm, 3),
                    "weight": WEIGHTS[name],
                    "evidence_class": EVIDENCE_CLASS[name],
                    "available": present,
                    "value_kind": "measured",
                }
            )
        classes: set[str] = {str(row["evidence_class"]) for row in indicator_rows if row["available"]}
        missing = [INDICATOR_LABELS[row["indicator"]] for row in indicator_rows if not row["available"]]
        score: float | None = None
        ranked_reason = ""
        if not can_normalise:
            ranked_reason = f"Fewer than {policy.MIN_ZONES_TO_RANK} zones have comparable data, so no ranking is made."
        elif len(classes) < policy.MIN_EVIDENCE_CLASSES_TO_RANK:
            ranked_reason = (
                f"Only {len(classes)} evidence class(es) present ({', '.join(sorted(classes)) or 'none'}); "
                f"{policy.MIN_EVIDENCE_CLASSES_TO_RANK} are required to rank."
            )
        else:
            available = [row for row in indicator_rows if row["normalised"] is not None]
            total_weight = float(sum(float(row["weight"]) for row in available))
            weighted = sum(float(row["weight"]) * float(row["normalised"]) for row in available)
            score = weighted / total_weight
            scored.append((zid, score))
            ranked_reason = "Ranked on the available geological and drilling evidence."
        confidence = "medium" if len(classes) >= 2 and entry["drillholes"] >= 5 else "low"
        entry.update(
            {
                "indicator_rows": indicator_rows,
                "evidence_classes": sorted(classes),
                "missing_inputs": missing,
                "score": None if score is None else round(score, 3),
                "rank": None,
                "confidence": confidence if score is not None else "low",
                "ranking_status": "ranked" if score is not None else "not_ranked",
                "ranking_reason": ranked_reason,
                "value_kind": "index",
            }
        )

    scored.sort(key=lambda item: item[1], reverse=True)
    rank_of = {zid: position + 1 for position, (zid, _score) in enumerate(scored)}
    for entry in per_zone:
        entry["rank"] = rank_of.get(entry["zone_id"])
    per_zone.sort(key=lambda e: (e["rank"] is None, e["rank"] or 0, e["zone_id"]))
    return {
        "zones": per_zone,
        "weights": WEIGHTS,
        "cutoff_pct": cutoff,
        "min_zones_to_rank": policy.MIN_ZONES_TO_RANK,
        "min_evidence_classes_to_rank": policy.MIN_EVIDENCE_CLASSES_TO_RANK,
        "ranking_enabled": can_normalise,
        "required_inputs": list(REQUIRED_INPUTS),
    }


def zone_inputs_from_geojson(collection: dict[str, Any], holes: pd.DataFrame) -> list[ZoneInput]:
    inputs: list[ZoneInput] = []
    for feature in collection.get("features", []):
        props = feature.get("properties") or {}
        zone_id = str(props.get("zone_id", ""))
        if not zone_id:
            continue
        host = props.get("host_unit_mapped")
        inputs.append(
            ZoneInput(
                zone_id=zone_id,
                name=str(props.get("name") or zone_id),
                area_km2=polygon_area_km2(feature.get("geometry") or {}),
                host_unit_mapped=bool(host) if isinstance(host, bool) else None,
                holes=_holes_in_zone(holes, zone_id),
            )
        )
    return inputs
