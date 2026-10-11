"""SYNTHETIC geology and geometry for the demonstration (not real survey or licence data).

The demonstration area, mine outlines, exploration zones and drillhole grades below are invented
for illustration. They are deterministic so that results are reproducible, and every feature
carries ``is_synthetic: true``. Nothing here should be used for mineral or boundary decisions.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

GEO_GENERATOR_VERSION = "synthetic-geo-v1.0"
DEMO_ZONES_DATASET_ID = "demo-synthetic-exploration-zones-v1"
DEMO_DRILLHOLES_DATASET_ID = "demo-synthetic-drillholes-v1"
SEED = 26009
AOI_BBOX = (80.00, 21.70, 80.40, 22.00)  # minLon, minLat, maxLon, maxLat (illustrative only)

SYNTHETIC_NOTE = "SYNTHETIC demonstration feature. Not a survey, licence or legal boundary."


def _rect(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> dict[str, Any]:
    ring = [
        [min_lon, min_lat],
        [max_lon, min_lat],
        [max_lon, max_lat],
        [min_lon, max_lat],
        [min_lon, min_lat],
    ]
    return {"type": "Polygon", "coordinates": [ring]}


def _poly(points: list[tuple[float, float]]) -> dict[str, Any]:
    ring = [[lon, lat] for lon, lat in points]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def demo_aoi_feature() -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {
            "feature_type": "aoi",
            "name": "Demonstration area",
            "is_synthetic": True,
            "note": "Illustrative rectangle in central India. Not a licence or concession boundary.",
        },
        "geometry": _rect(*AOI_BBOX),
    }


MINE_OUTLINES: tuple[tuple[str, str, tuple[float, float, float, float]], ...] = (
    ("SYN-A", "Synthetic Mine A", (80.10, 21.80, 80.18, 21.86)),
    ("SYN-B", "Synthetic Mine B", (80.22, 21.78, 80.30, 21.84)),
    ("SYN-C", "Synthetic Mine C", (80.12, 21.90, 80.20, 21.95)),
)


def demo_mine_features() -> list[dict[str, Any]]:
    return [
        {
            "type": "Feature",
            "properties": {
                "feature_type": "mine_boundary",
                "mine_id": mine_id,
                "name": name,
                "is_synthetic": True,
                "note": SYNTHETIC_NOTE,
            },
            "geometry": _rect(*bounds),
        }
        for mine_id, name, bounds in MINE_OUTLINES
    ]


# Exploration zones. Evidence columns are synthetic attributes of the mapped geology:
#   host_unit_mapped: whether the (synthetic) geological map shows the host unit in the zone.
EXPLORATION_ZONES: tuple[dict[str, Any], ...] = (
    {"zone_id": "EZ-01", "name": "Demo zone 1", "bounds": (80.02, 21.72, 80.09, 21.79), "host_unit_mapped": True},
    {"zone_id": "EZ-02", "name": "Demo zone 2", "bounds": (80.12, 21.72, 80.20, 21.78), "host_unit_mapped": True},
    {"zone_id": "EZ-03", "name": "Demo zone 3", "bounds": (80.26, 21.72, 80.34, 21.78), "host_unit_mapped": True},
    {"zone_id": "EZ-04", "name": "Demo zone 4", "bounds": (80.04, 21.90, 80.10, 21.97), "host_unit_mapped": True},
    {"zone_id": "EZ-05", "name": "Demo zone 5", "bounds": (80.27, 21.88, 80.36, 21.96), "host_unit_mapped": False},
    {"zone_id": "EZ-06", "name": "Demo zone 6", "bounds": (80.30, 21.92, 80.38, 21.99), "host_unit_mapped": True},
)

# Mean synthetic grade by zone (percent Mn). None = no drilling in this zone (demonstrates gaps).
DRILL_MEAN_MN: dict[str, float | None] = {
    "EZ-01": 31.0,
    "EZ-02": 24.0,
    "EZ-03": 17.0,
    "EZ-04": None,
    "EZ-05": None,
    "EZ-06": 11.0,
}


def demo_zone_features() -> list[dict[str, Any]]:
    features = []
    for zone in EXPLORATION_ZONES:
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "zone_id": zone["zone_id"],
                    "name": zone["name"],
                    "host_unit_mapped": zone["host_unit_mapped"],
                    "is_synthetic": True,
                    "note": SYNTHETIC_NOTE,
                },
                "geometry": _rect(*zone["bounds"]),
            }
        )
    return features


def demo_zones_collection() -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": demo_zone_features()}


def demo_drillholes() -> pd.DataFrame:
    """Synthetic drillhole collars and grade intercepts. Values are invented for demonstration."""
    rng = np.random.default_rng(SEED)
    rows: list[dict[str, Any]] = []
    counter = 1
    for zone in EXPLORATION_ZONES:
        mean = DRILL_MEAN_MN[zone["zone_id"]]
        if mean is None:
            continue
        min_lon, min_lat, max_lon, max_lat = zone["bounds"]
        holes = 6 if mean >= 20 else 5
        for _ in range(holes):
            lon = float(rng.uniform(min_lon + 0.005, max_lon - 0.005))
            lat = float(rng.uniform(min_lat + 0.005, max_lat - 0.005))
            grade = float(np.clip(rng.normal(mean, 4.0), 2.0, 45.0))
            rows.append(
                {
                    "hole_id": f"SYN-DH-{counter:03d}",
                    "zone_id": zone["zone_id"],
                    "lon": round(lon, 5),
                    "lat": round(lat, 5),
                    "depth_m": round(float(rng.uniform(30, 90)), 1),
                    "mn_pct": round(grade, 2),
                    "is_synthetic": True,
                }
            )
            counter += 1
    return pd.DataFrame(rows)
