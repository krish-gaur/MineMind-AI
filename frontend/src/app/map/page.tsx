"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import dynamicImport from "next/dynamic";
import { SyntheticBanner } from "@/components/data/SyntheticBanner";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  LayerToggles,
  RainfallPanel,
  SatellitePanel,
  StatusLegend,
  ZoneDetail,
  ZoneList,
  ZonesError,
} from "@/components/map/MapPanels";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState, LoadingBlock, Skeleton } from "@/components/ui/States";
import { useDatasets } from "@/lib/dataset-context";
import type { ExplorationResponse } from "@/lib/exploration-types";
import { useApiResource } from "@/lib/useApiResource";

const MineMap = dynamicImport(() => import("@/components/map/MineMap"), {
  ssr: false,
  loading: () => <Skeleton className="h-[460px] w-full lg:h-[620px]" />,
});

type FC = { type: "FeatureCollection"; features: unknown[] };
type LayersResponse = { aoi_bbox: number[]; layers: { id: string; label: string; is_synthetic: boolean; note: string }[]; attribution: { basemap: string } };
type SceneFC = { type: "FeatureCollection"; features: unknown[] };

const DEFAULT_BOUNDS: [number, number, number, number] = [80.0, 21.7, 80.4, 22.0];
const DEMO_ZONES_ID = "demo-synthetic-exploration-zones-v1";
const DEMO_HOLES_ID = "demo-synthetic-drillholes-v1";

export default function MapPage() {
  const { datasets, datasetsError, reloadDatasets } = useDatasets();
  const zonesDatasets = datasets?.filter((d) => d.kind === "exploration_zones") ?? null;
  const holesDatasets = datasets?.filter((d) => d.kind === "drillholes") ?? null;
  const [zonesId, setZonesId] = useState<string>(DEMO_ZONES_ID);
  const [holesId, setHolesId] = useState<string>(DEMO_HOLES_ID);

  if (datasetsError) {
    return (
      <>
        <PageHeader title="Geospatial view" />
        <Card>
          <ZonesError error={datasetsError} onRetry={reloadDatasets} />
        </Card>
      </>
    );
  }
  if (datasets === null) return <LoadingBlock label="Loading datasets" />;

  return (
    <MapView
      zonesId={zonesId}
      holesId={holesId}
      onZones={setZonesId}
      onHoles={setHolesId}
      zonesOptions={zonesDatasets ?? []}
      holesOptions={holesDatasets ?? []}
    />
  );
}

function MapView({
  zonesId,
  holesId,
  onZones,
  onHoles,
  zonesOptions,
  holesOptions,
}: {
  zonesId: string;
  holesId: string;
  onZones: (id: string) => void;
  onHoles: (id: string) => void;
  zonesOptions: { id: string; name: string }[];
  holesOptions: { id: string; name: string }[];
}) {
  const layers = useApiResource<LayersResponse>("/api/geo/layers", { zones_dataset_id: zonesId });
  const aoi = useApiResource<FC>("/api/geo/layers/aoi");
  const mines = useApiResource<FC>("/api/geo/layers/mines");
  const zones = useApiResource<FC>("/api/geo/layers/zones", { dataset_id: zonesId });
  const exploration = useApiResource<ExplorationResponse>("/api/exploration", {
    zones_dataset_id: zonesId,
    drillholes_dataset_id: holesId,
  });
  const [selected, setSelected] = useState<string | null>(null);
  const [visibility, setVisibility] = useState({ aoi: true, mines: true, zones: true, scenes: true });
  const [cursor, setCursor] = useState<[number, number] | null>(null);
  const [scenes, setScenes] = useState<SceneFC | null>(null);

  const statusByZone = useMemo(
    () => Object.fromEntries((exploration.data?.zones ?? []).map((zone) => [zone.zone_id, zone.status])),
    [exploration.data],
  );
  const selectedZone = exploration.data?.zones.find((zone) => zone.zone_id === selected) ?? null;
  const bounds = (layers.data?.aoi_bbox as [number, number, number, number] | undefined) ?? DEFAULT_BOUNDS;
  const centre = { lat: (bounds[1] + bounds[3]) / 2, lon: (bounds[0] + bounds[2]) / 2 };
  const isSynthetic = Boolean(exploration.data?.banner);

  return (
    <>
      <PageHeader
        title="Geospatial view"
        description="Exploration zones, mine outlines and public satellite footprints in one demonstration area. Zone colours show the kind of evidence, not a probability of mineralisation."
        status={
          cursor ? (
            <span className="font-mono text-xs text-ink-500" aria-live="off">
              {cursor[1].toFixed(4)}, {cursor[0].toFixed(4)}
            </span>
          ) : null
        }
      />
      {isSynthetic ? <SyntheticBanner text="Zones, mine outlines and drillhole grades here are invented for the demonstration. Do not use them for any real decision." /> : null}

      <div className="mt-5 grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-4">
          <div className="flex flex-wrap items-end gap-4 rounded-lg border border-line bg-surface p-4">
            <label className="flex flex-col gap-1 text-xs text-ink-500">
              Zone dataset
              <select
                value={zonesId}
                onChange={(event) => {
                  onZones(event.target.value);
                  setSelected(null);
                }}
                className="rounded-md border border-line-strong bg-white px-2.5 py-2 text-sm text-ink-900"
              >
                {zonesOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-ink-500">
              Drillhole dataset
              <select
                value={holesId}
                onChange={(event) => onHoles(event.target.value)}
                className="rounded-md border border-line-strong bg-white px-2.5 py-2 text-sm text-ink-900"
              >
                {holesOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="ml-auto">
              <LayerToggles value={visibility} onChange={setVisibility} />
            </div>
          </div>

          {zones.loading || aoi.loading || mines.loading ? (
            <Skeleton className="h-[460px] w-full lg:h-[620px]" />
          ) : zones.error ? (
            <Card>
              <ZonesError error={zones.error} onRetry={zones.reload} />
            </Card>
          ) : zones.data && aoi.data && mines.data ? (
            <MineMap
              aoi={aoi.data}
              mines={mines.data}
              zones={zones.data}
              scenes={scenes}
              statusByZone={statusByZone}
              selectedZoneId={selected}
              visibility={visibility}
              onSelectZone={setSelected}
              onCursor={(lon, lat) => setCursor([lon, lat])}
              bounds={bounds}
            />
          ) : null}

          <div className="flex flex-wrap items-center justify-between gap-4">
            <StatusLegend />
            <p className="text-xs text-ink-500">
              Basemap: Natural Earth country outlines (public domain), bundled offline. Set NEXT_PUBLIC_MAP_STYLE_URL to
              use an online basemap.
            </p>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <SatellitePanel onResult={(body) => setScenes(scenesToCollection(body))} />
            <RainfallPanel lat={centre.lat} lon={centre.lon} />
          </div>
        </div>

        <aside className="space-y-4" aria-label="Zone list and evidence">
          <Card labelledBy="zone-list-title">
            <CardHeader
              id="zone-list-title"
              title="Exploration zones"
              description="Keyboard-accessible list. Selecting a zone highlights it on the map."
            />
            {exploration.loading ? (
              <LoadingBlock rows={4} />
            ) : exploration.error ? (
              <ZonesError error={exploration.error} onRetry={exploration.reload} />
            ) : exploration.data && exploration.data.zones.length > 0 ? (
              <ZoneList zones={exploration.data.zones} selected={selected} onSelect={setSelected} />
            ) : (
              <EmptyState title="No zones are available for this dataset." />
            )}
          </Card>
          <Card labelledBy="zone-detail-title">
            <CardHeader id="zone-detail-title" title="Zone evidence" />
            <ZoneDetail zone={selectedZone} />
            {exploration.data ? (
              <div className="border-t border-line px-5 py-4 text-xs text-ink-500">
                <p>
                  Ranking is {exploration.data.ranking_enabled ? "enabled" : "disabled"} for this set of zones. Ranks use
                  only geological and drilling evidence.
                </p>
                <Link href="/exploration" className="mt-2 inline-block font-medium text-forest-800 underline">
                  Open the exploration table and method
                </Link>
              </div>
            ) : null}
          </Card>
          {layers.data ? (
            <p className="text-xs text-ink-500">
              {layers.data.attribution.basemap} Zone layer: {layers.data.layers.find((l) => l.id === "zones")?.note}
            </p>
          ) : null}
        </aside>
      </div>
    </>
  );
}

function scenesToCollection(body: { scenes: { id: string; acquired: string | null; cloud_cover_pct: number | null; footprint: unknown }[] } | null): SceneFC | null {
  if (!body) return null;
  return {
    type: "FeatureCollection",
    features: body.scenes
      .filter((scene) => scene.footprint)
      .map((scene) => ({
        type: "Feature",
        properties: { id: scene.id, acquired: scene.acquired, cloud_cover_pct: scene.cloud_cover_pct },
        geometry: scene.footprint,
      })),
  };
}
