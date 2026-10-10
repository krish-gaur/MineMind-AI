"""Geospatial layers, exploration gating, GeoJSON and drillhole ingestion, and public-service degradation."""

from __future__ import annotations

import json

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.exploration import ZoneInput, polygon_area_km2, score_zones
from app.domain.external import PublicJsonClient
from app.domain.synthetic_geo import DEMO_ZONES_DATASET_ID
from app.main import create_app

# ---------------------------------------------------------------------------
# Exploration scoring
# ---------------------------------------------------------------------------


def _holes(zone: str, grades: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"zone_id": [zone] * len(grades), "mn_pct": grades, "hole_id": [f"{zone}-{i}" for i in range(len(grades))]}
    )


def test_polygon_area_matches_hand_calculation() -> None:
    rectangle = {
        "type": "Polygon",
        "coordinates": [[[80.0, 21.8], [80.1, 21.8], [80.1, 21.9], [80.0, 21.9], [80.0, 21.8]]],
    }
    area = polygon_area_km2(rectangle)
    # 0.1 deg longitude x cos(21.85 deg) x 111.32 km, times 0.1 deg latitude x 110.574 km
    expected = 0.1 * 111.32 * 0.92759 * 0.1 * 110.574
    assert area == pytest.approx(expected, rel=0.01)


def test_zones_with_drilling_are_ranked_and_context_is_not_scored() -> None:
    zones = [
        ZoneInput("A", "A", 5.0, True, _holes("A", [30, 28, 25, 26, 27])),
        ZoneInput("B", "B", 5.0, True, _holes("B", [15, 12, 18, 14, 16])),
        ZoneInput("C", "C", 5.0, True, _holes("C", [22, 20, 21, 19, 23])),
    ]
    result = score_zones(zones)
    assert result["ranking_enabled"] is True
    ranked = [z["zone_id"] for z in result["zones"] if z["rank"] is not None]
    assert ranked == ["A", "C", "B"]
    for zone in result["zones"]:
        names = {row["indicator"] for row in zone["indicator_rows"]}
        assert names == {"host_unit_mapped", "mean_mn_pct", "share_high_grade"}  # nothing else is scored
        assert 0.0 <= zone["score"] <= 1.0
    assert sum(result["weights"].values()) == pytest.approx(1.0)


def test_a_zone_with_one_evidence_class_is_not_ranked() -> None:
    zones = [
        ZoneInput("A", "A", 5.0, True, _holes("A", [30, 28, 25, 26, 27])),
        ZoneInput("B", "B", 5.0, True, _holes("B", [15, 12, 18, 14, 16])),
        ZoneInput("C", "C", 5.0, True, _holes("C", [22, 20, 21, 19, 23])),
        ZoneInput("D", "D", 5.0, True, _holes("D", [])),  # map only: one evidence class
    ]
    result = score_zones(zones)
    zone_d = next(z for z in result["zones"] if z["zone_id"] == "D")
    assert zone_d["rank"] is None
    assert zone_d["ranking_status"] == "not_ranked"
    assert "Only 1 evidence class" in zone_d["ranking_reason"]


def test_ranking_is_disabled_when_too_few_zones_have_data() -> None:
    zones = [
        ZoneInput("A", "A", 5.0, True, _holes("A", [30, 28])),
        ZoneInput("B", "B", 5.0, None, _holes("B", [])),
    ]
    result = score_zones(zones)
    assert result["ranking_enabled"] is False
    assert all(z["rank"] is None for z in result["zones"])


def test_missing_inputs_are_listed_not_imputed() -> None:
    zones = [
        ZoneInput("A", "A", 5.0, True, _holes("A", [30, 28, 25])),
        ZoneInput("B", "B", 5.0, True, _holes("B", [15, 12, 18])),
        ZoneInput("C", "C", 5.0, True, _holes("C", [22, 20, 21])),
    ]
    result = score_zones(zones)
    zone = result["zones"][0]
    assert zone["missing_inputs"] == []
    # With no drilling in a zone, its grade indicators are missing, and the score uses only the map indicator.
    result_missing = score_zones([*zones, ZoneInput("D", "D", 5.0, True, _holes("D", []))])
    zone_d = next(z for z in result_missing["zones"] if z["zone_id"] == "D")
    assert any("Mean drillhole" in item for item in zone_d["missing_inputs"])
    assert zone_d["score"] is None  # one evidence class only, so no ranking


def test_demo_exploration_endpoint_labels_synthetic_and_gates_ranks(client: TestClient) -> None:
    body = client.get("/api/exploration").json()
    assert body["banner"] and "SYNTHETIC" in body["banner"]
    assert body["ranking_enabled"] is True
    ranks = {z["zone_id"]: z["rank"] for z in body["zones"]}
    assert ranks["EZ-01"] == 1  # highest grade, host unit mapped
    assert ranks["EZ-04"] is None and ranks["EZ-05"] is None  # no drilling: not ranked
    assert "NDVI" in " ".join(body["method"]["context_not_scored"])
    assert all(z["value_kind"] == "index" for z in body["zones"])
    assert "not a probability or a reserve estimate" in body["method"]["description"]


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

GOOD_POLY = {
    "type": "Polygon",
    "coordinates": [[[80.0, 21.7], [80.05, 21.7], [80.05, 21.75], [80.0, 21.75], [80.0, 21.7]]],
}
BOWTIE = {
    "type": "Polygon",
    "coordinates": [[[80.0, 21.7], [80.05, 21.75], [80.05, 21.7], [80.0, 21.75], [80.0, 21.7]]],
}


def _zones_file(features: list[dict]) -> bytes:  # type: ignore[type-arg]
    return json.dumps({"type": "FeatureCollection", "features": features}).encode("utf-8")


def test_zone_upload_keeps_valid_features_and_reports_invalid_ones(client: TestClient) -> None:
    payload = _zones_file(
        [
            {"type": "Feature", "properties": {"zone_id": "U-1", "host_unit_mapped": True}, "geometry": GOOD_POLY},
            {"type": "Feature", "properties": {"zone_id": "U-2"}, "geometry": BOWTIE},
            {
                "type": "Feature",
                "properties": {"zone_id": "U-3"},
                "geometry": {"type": "Point", "coordinates": [80, 21]},
            },
        ]
    )
    response = client.post(
        "/api/datasets",
        data={"kind": "exploration_zones", "name": "Pilot zones"},
        files={"file": ("zones.geojson", payload, "application/geo+json")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["kind"] == "exploration_zones"
    assert body["validation_status"] == "valid_with_warnings"
    assert any("invalid geometry" in note for note in body["validation_notes"])
    assert any("Polygon or MultiPolygon" in note for note in body["validation_notes"])
    assert body["zones"] == ["U-1"]
    layer = client.get("/api/geo/layers/zones", params={"dataset_id": body["id"]}).json()
    assert [f["properties"]["zone_id"] for f in layer["features"]] == ["U-1"]


def test_zone_upload_rejects_non_geojson(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        data={"kind": "exploration_zones"},
        files={"file": ("zones.geojson", b'{"type": "Feature"}', "application/geo+json")},
    )
    assert response.status_code == 422
    assert "FeatureCollection" in response.json()["error"]["message"]


def test_drillhole_upload_validates_ranges_and_feeds_the_ranking(client: TestClient) -> None:
    bad = b"hole_id,zone_id,lon,lat,depth_m,mn_pct\nH1,Z1,80.0,21.7,40,75\n"
    rejected = client.post("/api/datasets", data={"kind": "drillholes"}, files={"file": ("h.csv", bad, "text/csv")})
    assert rejected.status_code == 422
    assert "between 0 and 60" in json.dumps(rejected.json()["error"]["details"])

    missing = b"hole_id,zone_id,lon,lat\nH1,Z1,80.0,21.7\n"
    no_columns = client.post(
        "/api/datasets", data={"kind": "drillholes"}, files={"file": ("h.csv", missing, "text/csv")}
    )
    assert no_columns.status_code == 422
    assert "depth_m" in no_columns.json()["error"]["message"]

    good = b"hole_id,zone_id,lon,lat,depth_m,mn_pct\nH1,Z1,80.01,21.72,40,31\nH2,Z1,80.02,21.73,45,27\n"
    stored = client.post("/api/datasets", data={"kind": "drillholes"}, files={"file": ("h.csv", good, "text/csv")})
    assert stored.status_code == 201, stored.text
    assert stored.json()["row_count"] == 2
    assert stored.json()["source_type"] == "user_provided"


def test_layers_label_synthetic_content(client: TestClient) -> None:
    body = client.get("/api/geo/layers").json()
    by_id = {layer["id"]: layer for layer in body["layers"]}
    assert set(by_id) == {"aoi", "mines", "zones"}
    assert by_id["aoi"]["is_synthetic"] is True
    assert by_id["mines"]["count"] == 3
    aoi = client.get("/api/geo/layers/aoi").json()
    assert aoi["features"][0]["properties"]["is_synthetic"] is True
    assert client.get("/api/geo/layers/nope").status_code == 422


def test_exploration_rejects_a_mismatched_dataset_kind(client: TestClient) -> None:
    response = client.get("/api/exploration", params={"zones_dataset_id": "demo-synthetic-drillholes-v1"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "wrong_dataset_kind"


# ---------------------------------------------------------------------------
# Public services (mocked transports only; this sandbox cannot reach them)
# ---------------------------------------------------------------------------


def _client_with(tmp_path, handler, *, enabled: bool = True) -> TestClient:  # type: ignore[no-untyped-def]
    settings = Settings(
        app_env="test",
        log_level="WARNING",
        data_dir=tmp_path / "data",
        artifacts_dir=tmp_path / "artifacts",
        cors_origins="http://localhost:3000",
        enable_external_services=enabled,
        external_cache_ttl_h=24,
        external_timeout_s=2,
    )
    app = create_app(settings, http_transport=httpx.MockTransport(handler))
    return TestClient(app)


STAC_PAYLOAD = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": "S2A_TEST_1",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[80, 21.7], [80.4, 21.7], [80.4, 22], [80, 22], [80, 21.7]]],
            },
            "properties": {
                "datetime": "2026-09-20T04:00:00Z",
                "eo:cloud_cover": 12.3,
                "platform": "sentinel-2a",
                "s2:mgrs_tile": "44QLF",
            },
            "assets": {"thumbnail": {"href": "https://example.org/thumb.jpg"}},
        },
        {
            "type": "Feature",
            "id": "S2B_TEST_2",
            "geometry": None,
            "properties": {"datetime": "2026-09-10T04:00:00Z", "eo:cloud_cover": 88.0},
            "assets": {},
        },
    ],
}


def test_satellite_search_filters_clouds_and_normalises(tmp_path) -> None:  # type: ignore[no-untyped-def]
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        assert request.url.path.endswith("/search")
        assert request.url.params["collections"] == "sentinel-2-l2a"
        return httpx.Response(200, json=STAC_PAYLOAD)

    client = _client_with(tmp_path, handler)
    with client:
        first = client.get(
            "/api/geo/satellite/scenes", params={"start": "2026-09-01", "end": "2026-09-30", "max_cloud": 30}
        ).json()
        assert first["status"] == "live"
        assert [s["id"] for s in first["scenes"]] == ["S2A_TEST_1"]
        assert first["scenes"][0]["preview_url"] == "https://example.org/thumb.jpg"
        second = client.get(
            "/api/geo/satellite/scenes", params={"start": "2026-09-01", "end": "2026-09-30", "max_cloud": 30}
        ).json()
        assert second["status"] == "cached"
        assert calls["n"] == 1  # second call served from the disk cache


def test_satellite_timeout_is_reported_not_raised(tmp_path) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    with _client_with(tmp_path, handler) as client:
        body = client.get("/api/geo/satellite/scenes", params={"start": "2026-09-01", "end": "2026-09-30"}).json()
    assert body["status"] == "unavailable"
    assert "did not respond in time" in body["message"]
    assert body["scenes"] == []


def test_satellite_server_error_and_bad_json_degrade(tmp_path) -> None:  # type: ignore[no-untyped-def]
    def server_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="maintenance")

    with _client_with(tmp_path / "a", server_error) as client:
        body = client.get("/api/geo/satellite/scenes", params={"start": "2026-09-01", "end": "2026-09-30"}).json()
    assert body["status"] == "unavailable" and "HTTP 503" in body["message"]

    def not_json(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>portal</html>")

    with _client_with(tmp_path / "b", not_json) as client:
        body = client.get("/api/geo/satellite/scenes", params={"start": "2026-09-01", "end": "2026-09-30"}).json()
    assert body["status"] == "unavailable" and "not JSON" in body["message"]


def test_disabled_services_do_not_call_the_network(tmp_path) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("network must not be used when disabled")

    with _client_with(tmp_path, handler, enabled=False) as client:
        satellite = client.get("/api/geo/satellite/scenes", params={"start": "2026-09-01", "end": "2026-09-30"}).json()
        rain = client.get(
            "/api/geo/weather/daily", params={"lat": 21.8, "lon": 80.2, "start": "2026-09-01", "end": "2026-09-03"}
        ).json()
    assert satellite["status"] == "disabled"
    assert rain["status"] == "disabled"


OPEN_METEO = {"daily": {"time": ["2026-09-01", "2026-09-02", "2026-09-03"], "precipitation_sum": [0.0, None, 12.44]}}


def test_rainfall_keeps_missing_days_missing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["daily"] == "precipitation_sum"
        return httpx.Response(200, json=OPEN_METEO)

    with _client_with(tmp_path, handler) as client:
        body = client.get(
            "/api/geo/weather/daily", params={"lat": 21.8, "lon": 80.2, "start": "2026-09-01", "end": "2026-09-03"}
        ).json()
    assert body["status"] == "live"
    assert body["days"][1]["precipitation_mm"] is None
    assert body["missing_days"] == 1
    assert body["total_precipitation_mm"] == 12.4
    assert "CC BY 4.0" in body["source"]["licence"]


def test_rainfall_failure_is_explicit(tmp_path) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with _client_with(tmp_path, handler) as client:
        body = client.get(
            "/api/geo/weather/daily", params={"lat": 21.8, "lon": 80.2, "start": "2026-09-01", "end": "2026-09-03"}
        ).json()
    assert body["status"] == "unavailable"
    assert body["days"] == []


def test_scene_and_weather_inputs_are_validated(client: TestClient) -> None:
    assert client.get("/api/geo/satellite/scenes", params={"bbox": "1,2,3"}).status_code == 422
    assert client.get("/api/geo/satellite/scenes", params={"bbox": "80.4,21.7,80.0,22.0"}).status_code == 422
    assert (
        client.get(
            "/api/geo/weather/daily", params={"lat": 95, "lon": 80, "start": "2026-09-01", "end": "2026-09-02"}
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/geo/weather/daily", params={"lat": 21, "lon": 80, "start": "2026-09-05", "end": "2026-09-01"}
        ).status_code
        == 422
    )


def test_public_client_cache_is_keyed_by_request(tmp_path) -> None:  # type: ignore[no-untyped-def]
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"ok": True})

    client = PublicJsonClient(
        cache_dir=tmp_path, ttl_hours=1, timeout_s=2, enabled=True, transport=httpx.MockTransport(handler)
    )
    first = client.get_json("https://example.org/a", {"x": "1"}, cache_key="k1", service="svc")
    other = client.get_json("https://example.org/a", {"x": "2"}, cache_key="k2", service="svc")
    again = client.get_json("https://example.org/a", {"x": "1"}, cache_key="k1", service="svc")
    assert first.status == "live" and other.status == "live" and again.status == "cached"
    assert len(seen) == 2


def test_demo_zones_dataset_is_registered_as_synthetic(client: TestClient) -> None:
    body = client.get("/api/datasets", params={"kind": "exploration_zones"}).json()
    demo = next(d for d in body["datasets"] if d["id"] == DEMO_ZONES_DATASET_ID)
    assert demo["is_synthetic"] is True
