"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useMemo, useRef, useState } from "react";
import type {
  ExpressionSpecification,
  FilterSpecification,
  GeoJSONSource,
  Map as MapLibreMap,
  StyleSpecification,
} from "maplibre-gl";

export type FeatureCollectionLike = { type: "FeatureCollection"; features: unknown[] };

export type LayerVisibility = { aoi: boolean; mines: boolean; zones: boolean; scenes: boolean };

export type MineMapProps = {
  aoi: FeatureCollectionLike | null;
  mines: FeatureCollectionLike | null;
  zones: FeatureCollectionLike | null;
  scenes: FeatureCollectionLike | null;
  /** zone_id -> exploration status, used to colour zones (observed, inferred, ...). */
  statusByZone: Record<string, string>;
  selectedZoneId: string | null;
  visibility: LayerVisibility;
  onSelectZone: (zoneId: string) => void;
  onCursor: (lon: number, lat: number) => void;
  bounds: [number, number, number, number];
};

const OFFLINE_STYLE: StyleSpecification = {
  version: 8,
  name: "MineMind offline outline",
  sources: {
    context: {
      type: "geojson",
      data: "/geo/countries-context.geojson",
      attribution: "Natural Earth (public domain)",
    },
  },
  layers: [
    { id: "background", type: "background", paint: { "background-color": "#f6f4ee" } },
    { id: "context-fill", type: "fill", source: "context", paint: { "fill-color": "#e9e5da" } },
    { id: "context-line", type: "line", source: "context", paint: { "line-color": "#b9b2a2", "line-width": 0.8 } },
  ],
};

const EMPTY: FeatureCollectionLike = { type: "FeatureCollection", features: [] };

/**
 * The zone geometry carries no evidence status. Copy it from the exploration result so the map can colour
 * zones by status (observed, inferred, host unit not mapped, unavailable).
 */
function decorateZones(zones: FeatureCollectionLike | null, statusByZone: Record<string, string>): FeatureCollectionLike {
  if (!zones) return EMPTY;
  return {
    type: "FeatureCollection",
    features: zones.features.map((feature) => {
      const current = feature as { properties?: Record<string, unknown> };
      const zoneId = String(current.properties?.zone_id ?? "");
      return {
        ...current,
        properties: { ...(current.properties ?? {}), status: statusByZone[zoneId] ?? "unavailable" },
      };
    }),
  };
}

function styleFor(): StyleSpecification | string {
  const online = process.env.NEXT_PUBLIC_MAP_STYLE_URL;
  return online && online.trim() ? online.trim() : OFFLINE_STYLE;
}

const STATUS_FILL: ExpressionSpecification = [
  "match",
  ["get", "status"],
  "observed",
  "#1f4d3a",
  "inferred",
  "#c98a1b",
  "host_unit_not_mapped",
  "#9aa3a9",
  "#e9e5da",
];

/**
 * Interactive map. Data updates use setData and visibility uses layout properties, so changing a
 * filter does not rebuild the map. The map is decorative for keyboard users: every zone is also
 * available as a button next to the map.
 */
export default function MineMap(props: MineMapProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const latest = useRef(props);
  const zonesWithStatus = useMemo(
    () => decorateZones(props.zones, props.statusByZone),
    [props.zones, props.statusByZone],
  );

  useEffect(() => {
    latest.current = props;
  });

  useEffect(() => {
    let cancelled = false;
    let map: MapLibreMap | null = null;

    async function init() {
      try {
        const maplibre = await import("maplibre-gl");
        if (cancelled || !container.current) return;
        map = new maplibre.Map({
          container: container.current,
          style: styleFor(),
          bounds: latest.current.bounds as [number, number, number, number],
          fitBoundsOptions: { padding: 64, duration: 0 },
          attributionControl: { compact: true },
          canvasContextAttributes: { antialias: true },
        });
        map.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-right");
        map.addControl(new maplibre.ScaleControl({ unit: "metric" }), "bottom-left");
        mapRef.current = map;
        const instance = map;

        instance.on("load", () => {
          if (cancelled) return;
          const empty = EMPTY as unknown as GeoJSON.FeatureCollection;
          instance.addSource("aoi", { type: "geojson", data: empty });
          instance.addSource("mines", { type: "geojson", data: empty });
          instance.addSource("zones", { type: "geojson", data: empty });
          instance.addSource("scenes", { type: "geojson", data: empty });

          instance.addLayer({ id: "scenes-fill", type: "fill", source: "scenes", paint: { "fill-color": "#5e7bb0", "fill-opacity": 0.12 } });
          instance.addLayer({ id: "scenes-line", type: "line", source: "scenes", paint: { "line-color": "#5e7bb0", "line-width": 1.2 } });
          instance.addLayer({ id: "mines-fill", type: "fill", source: "mines", paint: { "fill-color": "#10291f", "fill-opacity": 0.12 } });
          instance.addLayer({ id: "mines-line", type: "line", source: "mines", paint: { "line-color": "#10291f", "line-width": 2.2 } });
          instance.addLayer({ id: "zones-fill", type: "fill", source: "zones", paint: { "fill-color": STATUS_FILL, "fill-opacity": 0.42 } });
          instance.addLayer({
            id: "zones-line",
            type: "line",
            source: "zones",
            filter: ["!=", ["get", "status"], "inferred"] as FilterSpecification,
            paint: { "line-color": "#14191c", "line-width": 1 },
          });
          instance.addLayer({
            id: "zones-inferred-line",
            type: "line",
            source: "zones",
            filter: ["==", ["get", "status"], "inferred"] as FilterSpecification,
            paint: { "line-color": "#7a5110", "line-width": 1.6, "line-dasharray": [2, 2] },
          });
          instance.addLayer({
            id: "zones-selected",
            type: "line",
            source: "zones",
            filter: ["==", ["get", "zone_id"], "__none__"] as FilterSpecification,
            paint: { "line-color": "#c98a1b", "line-width": 3.5 },
          });
          instance.addLayer({ id: "aoi-line", type: "line", source: "aoi", paint: { "line-color": "#c98a1b", "line-width": 2, "line-dasharray": [4, 2] } });

          instance.on("click", "zones-fill", (event) => {
            const zoneId = event.features?.[0]?.properties?.zone_id;
            if (typeof zoneId === "string") latest.current.onSelectZone(zoneId);
          });
          instance.on("mouseenter", "zones-fill", () => {
            instance.getCanvas().style.cursor = "pointer";
          });
          instance.on("mouseleave", "zones-fill", () => {
            instance.getCanvas().style.cursor = "";
          });
          instance.on("mousemove", (event) => {
            latest.current.onCursor(event.lngLat.lng, event.lngLat.lat);
          });
          setReady(true);
        });
        instance.on("error", () => {
          if (!cancelled) setFailed("The map could not render in this browser. The zone list still works.");
        });
      } catch {
        if (!cancelled) setFailed("The map library could not load. The zone list still works.");
      }
    }

    void init();
    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    (map.getSource("aoi") as GeoJSONSource | undefined)?.setData((props.aoi ?? EMPTY) as GeoJSON.FeatureCollection);
    (map.getSource("mines") as GeoJSONSource | undefined)?.setData((props.mines ?? EMPTY) as GeoJSON.FeatureCollection);
    (map.getSource("zones") as GeoJSONSource | undefined)?.setData(zonesWithStatus as GeoJSON.FeatureCollection);
    (map.getSource("scenes") as GeoJSONSource | undefined)?.setData((props.scenes ?? EMPTY) as GeoJSON.FeatureCollection);
  }, [ready, props.aoi, props.mines, zonesWithStatus, props.scenes]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const visibility: Record<string, boolean> = {
      "aoi-line": props.visibility.aoi,
      "mines-fill": props.visibility.mines,
      "mines-line": props.visibility.mines,
      "zones-fill": props.visibility.zones,
      "zones-line": props.visibility.zones,
      "zones-inferred-line": props.visibility.zones,
      "zones-selected": props.visibility.zones,
      "scenes-fill": props.visibility.scenes,
      "scenes-line": props.visibility.scenes,
    };
    for (const [layer, on] of Object.entries(visibility)) {
      map.setLayoutProperty(layer, "visibility", on ? "visible" : "none");
    }
  }, [ready, props.visibility]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.setFilter("zones-selected", [
      "==",
      ["get", "zone_id"],
      props.selectedZoneId ?? "__none__",
    ] as FilterSpecification);
  }, [ready, props.selectedZoneId]);

  return (
    // MapLibre's stylesheet sets `position: relative` on its container, so the map container must not
    // rely on absolute positioning. The fixed-height wrapper sizes it instead.
    <div className="relative h-[460px] w-full overflow-hidden rounded-lg border border-line bg-paper lg:h-[620px]">
      <div
        ref={container}
        role="region"
        aria-label="Map of the demonstration area with exploration zones, mine outlines and satellite footprints"
        className="h-full w-full"
      />
      {failed ? (
        <div role="status" className="absolute inset-x-4 top-4 rounded-md border border-amber-500 bg-amber-50 p-3 text-sm text-amber-900">
          {failed}
        </div>
      ) : null}
    </div>
  );
}
