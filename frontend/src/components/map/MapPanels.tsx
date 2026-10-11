"use client";

import { useState } from "react";
import { apiGet } from "@/lib/api";
import { StatusPill, type Tone, ValueKindBadge } from "@/components/ui/Badges";
import { Card, CardHeader } from "@/components/ui/Card";
import { ErrorState, LoadingBlock } from "@/components/ui/States";
import { formatNumber, formatShortDate } from "@/lib/format";
import type { ExplorationResponse, ExplorationZone } from "@/lib/exploration-types";

export const STATUS_LABEL: Record<string, string> = {
  observed: "Drilling observed",
  inferred: "Host unit mapped, no drilling",
  host_unit_not_mapped: "Host unit not mapped",
  unavailable: "No geological data",
};

const STATUS_TONE: Record<string, Tone> = {
  observed: "good",
  inferred: "warn",
  host_unit_not_mapped: "neutral",
  unavailable: "neutral",
};

export function StatusLegend() {
  return (
    <ul aria-label="Map legend" className="flex flex-wrap gap-3 text-xs text-ink-700">
      <li className="flex items-center gap-1.5">
        <span className="inline-block h-3 w-3 rounded-sm bg-forest-700/60" aria-hidden="true" /> Drilling observed
      </li>
      <li className="flex items-center gap-1.5">
        <span className="inline-block h-3 w-3 rounded-sm border border-dashed border-amber-700 bg-amber-500/30" aria-hidden="true" />
        Host unit mapped, no drilling
      </li>
      <li className="flex items-center gap-1.5">
        <span className="inline-block h-3 w-3 rounded-sm bg-slate-300/60" aria-hidden="true" /> Host unit not mapped
      </li>
      <li className="flex items-center gap-1.5">
        <span className="inline-block h-3 w-3 rounded-sm bg-forest-900" aria-hidden="true" /> Mine outline (synthetic)
      </li>
      <li className="flex items-center gap-1.5">
        <span className="inline-block h-3 w-3 rounded-sm bg-[#5e7bb0]/30" aria-hidden="true" /> Sentinel-2 footprint
      </li>
    </ul>
  );
}

export function LayerToggles({
  value,
  onChange,
}: {
  value: { aoi: boolean; mines: boolean; zones: boolean; scenes: boolean };
  onChange: (next: { aoi: boolean; mines: boolean; zones: boolean; scenes: boolean }) => void;
}) {
  const items: { key: keyof typeof value; label: string }[] = [
    { key: "zones", label: "Exploration zones" },
    { key: "mines", label: "Mine outlines (synthetic)" },
    { key: "aoi", label: "Demonstration area" },
    { key: "scenes", label: "Sentinel-2 footprints" },
  ];
  return (
    <fieldset className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
      <legend className="sr-only">Map layers</legend>
      {items.map((item) => (
        <label key={item.key} className="flex items-center gap-2 text-ink-900">
          <input
            type="checkbox"
            className="h-4 w-4 accent-forest-800"
            checked={value[item.key]}
            onChange={(event) => onChange({ ...value, [item.key]: event.target.checked })}
          />
          {item.label}
        </label>
      ))}
    </fieldset>
  );
}

export function ZoneList({
  zones,
  selected,
  onSelect,
}: {
  zones: ExplorationZone[];
  selected: string | null;
  onSelect: (zoneId: string) => void;
}) {
  return (
    <ul className="divide-y divide-line">
      {zones.map((zone) => {
        const active = zone.zone_id === selected;
        return (
          <li key={zone.zone_id}>
            <button
              type="button"
              onClick={() => onSelect(zone.zone_id)}
              aria-pressed={active}
              className={`flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left text-sm transition-colors ${
                active ? "bg-forest-50" : "hover:bg-slate-100"
              }`}
            >
              <span className="min-w-0">
                <span className="block font-mono text-xs font-semibold text-ink-900">{zone.zone_id}</span>
                <span className="block truncate text-xs text-ink-500">{STATUS_LABEL[zone.status] ?? zone.status}</span>
              </span>
              <span className="shrink-0 text-right text-xs text-ink-700">
                {zone.rank !== null ? `Rank ${zone.rank}` : "Not ranked"}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export function ZoneDetail({ zone }: { zone: ExplorationZone | null }) {
  if (!zone) {
    return (
      <p className="p-5 text-sm text-ink-500">Select a zone on the map or in the list to see its evidence.</p>
    );
  }
  return (
    <div className="space-y-4 p-5 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm font-semibold text-ink-900">{zone.zone_id}</span>
        <StatusPill tone={STATUS_TONE[zone.status] ?? "neutral"}>{STATUS_LABEL[zone.status] ?? zone.status}</StatusPill>
        <ValueKindBadge kind="index" />
      </div>
      <dl className="grid grid-cols-2 gap-3">
        <div>
          <dt className="text-xs text-ink-500">Priority index (0 to 1)</dt>
          <dd className="tabular font-mono font-semibold">{zone.score === null ? "not computed" : zone.score.toFixed(2)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-500">Rank</dt>
          <dd className="tabular font-mono font-semibold">{zone.rank ?? "not ranked"}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-500">Drillholes</dt>
          <dd className="tabular font-mono">{formatNumber(zone.drillholes)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-500">Area (approx.)</dt>
          <dd className="tabular font-mono">{zone.area_km2 === null ? "n/a" : `${formatNumber(zone.area_km2, 1)} km²`}</dd>
        </div>
      </dl>
      <p className="text-xs text-ink-700">{zone.ranking_reason}</p>
      <div className="overflow-x-auto rounded border border-line">
        <table className="w-full min-w-[420px] text-left text-xs">
          <caption className="sr-only">Indicators for zone {zone.zone_id}</caption>
          <thead className="bg-slate-100 text-ink-700">
            <tr>
              <th scope="col" className="px-2 py-1.5 font-semibold">Indicator</th>
              <th scope="col" className="px-2 py-1.5 text-right font-semibold">Value</th>
              <th scope="col" className="px-2 py-1.5 text-right font-semibold">Weight</th>
            </tr>
          </thead>
          <tbody>
            {zone.indicator_rows.map((row) => (
              <tr key={row.indicator} className="border-t border-line">
                <td className="px-2 py-1.5">{row.label}</td>
                <td className="tabular px-2 py-1.5 text-right font-mono">
                  {row.available ? formatNumber(row.value ?? null, row.indicator === "share_high_grade" ? 2 : 1) : "missing"}
                </td>
                <td className="tabular px-2 py-1.5 text-right font-mono">{Math.round(row.weight * 100)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {zone.missing_inputs.length > 0 ? (
        <div>
          <p className="text-xs font-semibold text-ink-700">Missing inputs (not imputed)</p>
          <ul className="mt-1 list-disc pl-5 text-xs text-ink-700">
            {zone.missing_inputs.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <p className="text-[11px] text-ink-500">
        Context only, not scored: vegetation, rainfall, soil moisture and surface temperature indices.
      </p>
    </div>
  );
}

type SceneResponse = {
  status: string;
  message: string;
  retrieved_at: string | null;
  scenes: { id: string; acquired: string | null; cloud_cover_pct: number | null; footprint: unknown; tile: string | null }[];
  source: { attribution: string };
};

export function SatellitePanel({
  onResult,
}: {
  onResult: (scenes: SceneResponse | null) => void;
}) {
  const [state, setState] = useState<{ loading: boolean; error: string | null; response: SceneResponse | null }>({
    loading: false,
    error: null,
    response: null,
  });
  return (
    <Card labelledBy="sat-title">
      <CardHeader
        id="sat-title"
        title="Sentinel-2 scene footprints"
        description="Scene metadata from the public Copernicus catalogue. No imagery is processed in this release."
        actions={<ValueKindBadge kind="measured" />}
      />
      <div className="space-y-3 p-5 text-sm">
        <button
          type="button"
          disabled={state.loading}
          onClick={async () => {
            setState({ loading: true, error: null, response: null });
            try {
              const today = new Date();
              const end = today.toISOString().slice(0, 10);
              const startDate = new Date(today.getTime() - 90 * 86400000).toISOString().slice(0, 10);
              const body = await apiGet<SceneResponse>("/api/geo/satellite/scenes", {
                start: startDate,
                end,
                max_cloud: 30,
                limit: 20,
              });
              setState({ loading: false, error: null, response: body });
              onResult(body);
            } catch {
              setState({ loading: false, error: "The scene search could not be completed. Try again later.", response: null });
              onResult(null);
            }
          }}
          className="rounded-md border border-line-strong bg-white px-3 py-2 text-sm font-medium text-ink-900 hover:bg-slate-100 disabled:opacity-60"
        >
          {state.loading ? "Searching..." : "Search last 90 days (cloud cover up to 30%)"}
        </button>
        {state.error ? <p role="alert" className="text-brick-700">{state.error}</p> : null}
        {state.response ? (
          <div role="status" className="space-y-1 text-ink-700">
            <p>
              <span className="font-semibold text-ink-900">Status: {state.response.status}.</span> {state.response.message}
            </p>
            <p>
              {state.response.scenes.length} scene(s) match. Attribution: {state.response.source.attribution}
            </p>
            {state.response.scenes.slice(0, 5).map((scene) => (
              <p key={scene.id} className="font-mono text-xs">
                {formatShortDate((scene.acquired ?? "").slice(0, 10))} · {scene.cloud_cover_pct ?? "n/a"}% cloud · {scene.tile ?? "tile n/a"}
              </p>
            ))}
          </div>
        ) : null}
      </div>
    </Card>
  );
}

type WeatherResponse = {
  status: string;
  message: string;
  total_precipitation_mm: number | null;
  missing_days: number;
  days: { date: string; precipitation_mm: number | null }[];
  source: { attribution: string; licence: string };
};

export function RainfallPanel({ lat, lon }: { lat: number; lon: number }) {
  const [state, setState] = useState<{ loading: boolean; error: string | null; response: WeatherResponse | null }>({
    loading: false,
    error: null,
    response: null,
  });
  return (
    <Card labelledBy="rain-title">
      <CardHeader
        id="rain-title"
        title="Daily rainfall at the demonstration area"
        description="Public reanalysis at one point, not a station at a mine. It is context only."
        actions={<ValueKindBadge kind="measured" />}
      />
      <div className="space-y-3 p-5 text-sm">
        <button
          type="button"
          disabled={state.loading}
          onClick={async () => {
            setState({ loading: true, error: null, response: null });
            try {
              const today = new Date();
              const end = new Date(today.getTime() - 7 * 86400000).toISOString().slice(0, 10);
              const start = new Date(today.getTime() - 37 * 86400000).toISOString().slice(0, 10);
              const body = await apiGet<WeatherResponse>("/api/geo/weather/daily", { lat, lon, start, end });
              setState({ loading: false, error: null, response: body });
            } catch {
              setState({ loading: false, error: "The rainfall request could not be completed. Try again later.", response: null });
            }
          }}
          className="rounded-md border border-line-strong bg-white px-3 py-2 text-sm font-medium text-ink-900 hover:bg-slate-100 disabled:opacity-60"
        >
          {state.loading ? "Fetching..." : "Fetch the last 30 days"}
        </button>
        {state.error ? <p role="alert" className="text-brick-700">{state.error}</p> : null}
        {state.response ? (
          <div role="status" className="space-y-1 text-ink-700">
            <p>
              <span className="font-semibold text-ink-900">Status: {state.response.status}.</span> {state.response.message}
            </p>
            {state.response.total_precipitation_mm !== null ? (
              <p>
                Total {formatNumber(state.response.total_precipitation_mm, 1)} mm over {state.response.days.length} day(s);{" "}
                {state.response.missing_days} day(s) missing (not treated as zero).
              </p>
            ) : null}
            <p className="text-xs text-ink-500">{state.response.source.licence}</p>
          </div>
        ) : null}
      </div>
    </Card>
  );
}

export function ZoneLoading() {
  return <LoadingBlock label="Loading zones" rows={4} />;
}

export function ZonesError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  return <ErrorState error={error} onRetry={onRetry} title="Zones could not be loaded" />;
}

export type { ExplorationResponse };
