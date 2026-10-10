"""Exploration-zone prioritisation (evidence-gated index)."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_store
from app.domain.exploration import score_zones, zone_inputs_from_geojson
from app.domain.provenance import SOURCE_LABELS, SourceType
from app.domain.store import DatasetStore
from app.domain.synthetic_geo import DEMO_DRILLHOLES_DATASET_ID, DEMO_ZONES_DATASET_ID
from app.errors import AppError

router = APIRouter(tags=["exploration"])


@router.get("/exploration", summary="Rank exploration zones on geological and drilling evidence")
def exploration(
    zones_dataset_id: str | None = Query(default=None),
    drillholes_dataset_id: str | None = Query(default=None),
    store: DatasetStore = Depends(get_store),
) -> dict[str, Any]:
    zones_id = zones_dataset_id or DEMO_ZONES_DATASET_ID
    holes_id = drillholes_dataset_id or DEMO_DRILLHOLES_DATASET_ID
    zones_manifest = store.get_manifest(zones_id)
    if zones_manifest.kind != "exploration_zones":
        raise AppError(
            "zones_dataset_id must be an exploration zone dataset.", status_code=422, code="wrong_dataset_kind"
        )
    holes_manifest = store.get_manifest(holes_id)
    if holes_manifest.kind != "drillholes":
        raise AppError("drillholes_dataset_id must be a drillhole dataset.", status_code=422, code="wrong_dataset_kind")

    collection = json.loads(store.read_bytes(zones_id).decode("utf-8"))
    holes = pd.read_csv(store.data_path(holes_id), dtype={"hole_id": str, "zone_id": str})
    result = score_zones(zone_inputs_from_geojson(collection, holes))

    def context(manifest: Any) -> dict[str, Any]:
        source = SourceType(manifest.source_type)
        return {
            "id": manifest.id,
            "name": manifest.name,
            "source_type": source.value,
            "source_label": SOURCE_LABELS[source],
            "is_synthetic": source is SourceType.SYNTHETIC,
            "row_count": manifest.row_count,
        }

    is_synthetic = SourceType(zones_manifest.source_type) is SourceType.SYNTHETIC or (
        SourceType(holes_manifest.source_type) is SourceType.SYNTHETIC
    )
    banner = (
        "SYNTHETIC DEMONSTRATION DATA. Zones and grades are invented. The ranking shows how the method works and "
        "is not an exploration finding."
        if is_synthetic
        else None
    )
    return {
        "datasets": {"zones": context(zones_manifest), "drillholes": context(holes_manifest)},
        "banner": banner,
        "ranking_enabled": result["ranking_enabled"],
        "zones": result["zones"],
        "method": {
            "weights": result["weights"],
            "high_grade_cutoff_pct": result["cutoff_pct"],
            "min_zones_to_rank": result["min_zones_to_rank"],
            "min_evidence_classes_to_rank": result["min_evidence_classes_to_rank"],
            "description": (
                "Each scored indicator is min-max normalised across zones. The index is the weighted mean of the "
                "available normalised indicators, with weights renormalised over those available. The index is "
                "not a probability or a reserve estimate."
            ),
            "context_not_scored": [
                "Vegetation indices (for example NDVI)",
                "Rainfall, soil moisture and land-surface temperature",
                "Radar (SAR) backscatter",
            ],
            "context_reason": (
                "These respond to many non-mineral processes. Using them as evidence would present vegetation or "
                "moisture as proof of manganese, which the data does not support."
            ),
        },
        "required_inputs": result["required_inputs"],
        "notes": [
            "A zone with one evidence class (for example, a mapped host unit but no drilling) is listed unranked.",
            "Map and drilling evidence must be validated by a geologist before any ranking informs drilling decisions.",
        ],
    }
