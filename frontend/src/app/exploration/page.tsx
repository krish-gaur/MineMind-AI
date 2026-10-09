"use client";

import Link from "next/link";
import { useState } from "react";
import { SyntheticBanner } from "@/components/data/SyntheticBanner";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatusPill, type Tone, ValueKindBadge } from "@/components/ui/Badges";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingBlock, Skeleton } from "@/components/ui/States";
import { STATUS_LABEL } from "@/components/map/MapPanels";
import { useDatasets } from "@/lib/dataset-context";
import { formatNumber } from "@/lib/format";
import type { ExplorationResponse } from "@/lib/exploration-types";
import { useApiResource } from "@/lib/useApiResource";

const DEMO_ZONES_ID = "demo-synthetic-exploration-zones-v1";
const DEMO_HOLES_ID = "demo-synthetic-drillholes-v1";
const STATUS_TONE: Record<string, Tone> = {
  observed: "good",
  inferred: "warn",
  host_unit_not_mapped: "neutral",
  unavailable: "neutral",
};

export default function ExplorationPage() {
  const { datasets, datasetsError, reloadDatasets } = useDatasets();
  const [zonesId, setZonesId] = useState(DEMO_ZONES_ID);
  const [holesId, setHolesId] = useState(DEMO_HOLES_ID);

  if (datasetsError) {
    return (
      <>
        <PageHeader title="Exploration zones" />
        <Card>
          <ErrorState error={datasetsError} onRetry={reloadDatasets} title="Datasets could not be loaded" />
        </Card>
      </>
    );
  }
  if (datasets === null) return <LoadingBlock label="Loading datasets" />;
  const zonesOptions = datasets.filter((d) => d.kind === "exploration_zones");
  const holesOptions = datasets.filter((d) => d.kind === "drillholes");
  return (
    <ExplorationView
      zonesId={zonesId}
      holesId={holesId}
      onZones={setZonesId}
      onHoles={setHolesId}
      zonesOptions={zonesOptions}
      holesOptions={holesOptions}
    />
  );
}

function ExplorationView({
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
  const { data, error, loading, reload, refreshing } = useApiResource<ExplorationResponse>("/api/exploration", {
    zones_dataset_id: zonesId,
    drillholes_dataset_id: holesId,
  });
  return (
    <>
      <PageHeader
        title="Exploration zones"
        description="Priority index for exploration zones, built only from geological and drilling evidence. It shows where to look first, not whether manganese is present."
        status={<span aria-live="polite" className="text-xs text-ink-500">{refreshing ? "Updating..." : ""}</span>}
      />
      {data?.banner ? (
        <SyntheticBanner text={data.banner.replace(/^SYNTHETIC DEMONSTRATION DATA\.?\s*/, "")} />
      ) : null}

      <div className="mt-5 flex flex-wrap gap-4 rounded-lg border border-line bg-surface p-4">
        <label className="flex flex-col gap-1 text-xs text-ink-500">
          Zone dataset
          <select value={zonesId} onChange={(e) => onZones(e.target.value)} className="rounded-md border border-line-strong bg-white px-2.5 py-2 text-sm text-ink-900">
            {zonesOptions.map((option) => (
              <option key={option.id} value={option.id}>{option.name}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-ink-500">
          Drillhole dataset
          <select value={holesId} onChange={(e) => onHoles(e.target.value)} className="rounded-md border border-line-strong bg-white px-2.5 py-2 text-sm text-ink-900">
            {holesOptions.map((option) => (
              <option key={option.id} value={option.id}>{option.name}</option>
            ))}
          </select>
        </label>
        <p className="ml-auto max-w-md self-end text-xs text-ink-500">
          Upload your own zones (GeoJSON) or drillholes (CSV) on the{" "}
          <Link href="/data" className="font-medium text-forest-800 underline">Data page</Link>.
        </p>
      </div>

      {error ? (
        <div className="mt-5">
          <Card>
            <ErrorState error={error} onRetry={reload} />
          </Card>
        </div>
      ) : null}
      {loading && !error ? <Skeleton className="mt-6 h-96" /> : null}

      {data && !error ? (
        <div className="mt-6 space-y-6">
          <Card labelledBy="ranking-title">
            <CardHeader
              id="ranking-title"
              title="Zone ranking and evidence"
              description={data.method.description}
              actions={<ValueKindBadge kind="index" />}
            />
            {data.zones.length === 0 ? (
              <div className="p-5"><EmptyState title="No zones in this dataset." /></div>
            ) : (
              <div className="overflow-x-auto p-5">
                <table className="w-full min-w-[900px] text-left text-sm">
                  <caption className="sr-only">Exploration zones with status, indicators, index and rank</caption>
                  <thead className="bg-slate-100 text-xs uppercase tracking-wide text-ink-700">
                    <tr>
                      <th scope="col" className="px-3 py-2 font-semibold">Zone</th>
                      <th scope="col" className="px-3 py-2 font-semibold">Evidence status</th>
                      <th scope="col" className="px-3 py-2 text-right font-semibold">Drillholes</th>
                      <th scope="col" className="px-3 py-2 text-right font-semibold">Mean Mn (%)</th>
                      <th scope="col" className="px-3 py-2 text-right font-semibold">Intercepts ≥ cut-off</th>
                      <th scope="col" className="px-3 py-2 text-right font-semibold">Index (0 to 1)</th>
                      <th scope="col" className="px-3 py-2 font-semibold">Rank</th>
                      <th scope="col" className="px-3 py-2 font-semibold">Why</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.zones.map((zone) => {
                      const mean = zone.indicator_rows.find((row) => row.indicator === "mean_mn_pct");
                      const share = zone.indicator_rows.find((row) => row.indicator === "share_high_grade");
                      return (
                        <tr key={zone.zone_id} className="border-t border-line align-top">
                          <td className="whitespace-nowrap px-3 py-2 font-mono text-xs font-semibold">{zone.zone_id}</td>
                          <td className="px-3 py-2">
                            <StatusPill tone={STATUS_TONE[zone.status] ?? "neutral"}>{STATUS_LABEL[zone.status] ?? zone.status}</StatusPill>
                          </td>
                          <td className="tabular px-3 py-2 text-right">{formatNumber(zone.drillholes)}</td>
                          <td className="tabular px-3 py-2 text-right">{mean?.available ? formatNumber(mean.value ?? null, 1) : "missing"}</td>
                          <td className="tabular px-3 py-2 text-right">
                            {share?.available && share.value !== null ? `${formatNumber(share.value * 100, 0)}%` : "missing"}
                          </td>
                          <td className="tabular whitespace-nowrap px-3 py-2 text-right font-mono">
                            {zone.score === null ? "not computed" : zone.score.toFixed(2)}
                          </td>
                          <td className="px-3 py-2 font-semibold">{zone.rank ?? "-"}</td>
                          <td className="max-w-xs px-3 py-2 text-xs text-ink-700">{zone.ranking_reason}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <div className="grid gap-6 xl:grid-cols-2">
            <Card labelledBy="method-title">
              <CardHeader id="method-title" title="Method and weights" description={data.method.context_reason} />
              <div className="space-y-3 p-5 text-sm">
                <ul className="space-y-1.5">
                  {Object.entries(data.method.weights).map(([key, weight]) => (
                    <li key={key} className="flex justify-between gap-4 border-b border-line pb-1.5">
                      <span>{key.replaceAll("_", " ")}</span>
                      <span className="tabular font-mono">{Math.round(weight * 100)}%</span>
                    </li>
                  ))}
                </ul>
                <p className="text-xs text-ink-500">
                  High-grade cut-off {data.method.high_grade_cutoff_pct}% Mn. Ranking needs at least{" "}
                  {data.method.min_zones_to_rank} zones with data and {data.method.min_evidence_classes_to_rank} evidence
                  classes per zone.
                </p>
                <div>
                  <p className="text-xs font-semibold text-ink-700">Context only, not scored</p>
                  <ul className="mt-1 list-disc pl-5 text-xs text-ink-700">
                    {data.method.context_not_scored.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              </div>
            </Card>
            <Card labelledBy="inputs-title">
              <CardHeader id="inputs-title" title="Inputs needed before any real assessment" description="This demonstration cannot replace these." />
              <ol className="list-decimal space-y-2 p-5 pl-9 text-sm text-ink-900">
                {data.required_inputs.map((item) => <li key={item}>{item}</li>)}
              </ol>
            </Card>
          </div>

          <Card labelledBy="ex-notes-title">
            <CardHeader id="ex-notes-title" title="Notes" />
            <ul className="list-disc space-y-2 p-5 pl-9 text-sm text-ink-700">
              {data.notes.map((note) => <li key={note}>{note}</li>)}
              <li>Index values are not probabilities and are not reserve or resource estimates.</li>
            </ul>
          </Card>
        </div>
      ) : null}
    </>
  );
}
