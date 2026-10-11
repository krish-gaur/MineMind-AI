"use client";

import Link from "next/link";
import { useState } from "react";
import { SyntheticBanner } from "@/components/data/SyntheticBanner";
import { PageHeader } from "@/components/layout/PageHeader";
import { RecommendationCard } from "@/components/recs/RecommendationCard";
import { ScopeFilters } from "@/components/scope/ScopeFilters";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingBlock, Skeleton } from "@/components/ui/States";
import { useDatasets } from "@/lib/dataset-context";
import { formatDate } from "@/lib/format";
import type { DatasetSummary, RecommendationsResponse } from "@/lib/types";
import { useApiResource } from "@/lib/useApiResource";

export default function RecommendationsPage() {
  const { active, datasets, datasetsError, reloadDatasets } = useDatasets();
  if (datasetsError) {
    return (
      <>
        <PageHeader title="Recommendations" />
        <Card>
          <ErrorState error={datasetsError} onRetry={reloadDatasets} title="Datasets could not be loaded" />
        </Card>
      </>
    );
  }
  if (datasets === null) return <LoadingBlock label="Loading datasets" />;
  if (active === null) {
    return (
      <>
        <PageHeader title="Recommendations" />
        <Card>
          <EmptyState title="No production dataset is available yet." />
        </Card>
      </>
    );
  }
  return <RecommendationsView key={active.id} dataset={active} />;
}

function RecommendationsView({ dataset }: { dataset: DatasetSummary }) {
  const [mineId, setMineId] = useState("");
  const [zoneId, setZoneId] = useState("");
  const [horizon, setHorizon] = useState(30);
  const [includeForecast, setIncludeForecast] = useState(true);
  const params = {
    dataset_id: dataset.id,
    mine_id: mineId,
    zone_id: zoneId,
    horizon_days: horizon,
    include_forecast: includeForecast ? "true" : "false",
  };
  const { data, error, loading, refreshing, reload } = useApiResource<RecommendationsResponse>(
    "/api/recommendations",
    params,
  );

  const fired = data?.rules.filter((rule) => rule.fired) ?? [];
  const notFired = data?.rules.filter((rule) => !rule.fired) ?? [];

  return (
    <>
      <PageHeader
        title="Recommendations"
        description="Actions that follow from specific evidence in the data. Each one cites what triggered it, and rules that did not trigger are listed so silence is not mistaken for approval."
        status={
          <span aria-live="polite" className="text-xs text-ink-500">
            {refreshing ? "Updating..." : data?.as_of ? `Data as of ${formatDate(data.as_of)}` : ""}
          </span>
        }
      />
      {dataset.is_synthetic ? <SyntheticBanner text="Recommendations for synthetic data illustrate the rules. Do not act on them for MOIL." /> : null}

      <div className="mt-5 space-y-4">
        <ScopeFilters
          dataset={dataset}
          mineId={mineId}
          zoneId={zoneId}
          onMine={setMineId}
          onZone={setZoneId}
          horizon={horizon}
          onHorizon={setHorizon}
        >
          <label className="flex items-center gap-2 pb-2 text-sm text-ink-700">
            <input
              type="checkbox"
              className="h-4 w-4 accent-forest-800"
              checked={includeForecast}
              onChange={(event) => setIncludeForecast(event.target.checked)}
            />
            Include forecast-based rules
          </label>
        </ScopeFilters>
      </div>

      {error ? (
        <div className="mt-5">
          <Card>
            <ErrorState error={error} onRetry={reload} />
          </Card>
        </div>
      ) : null}
      {loading && !error ? (
        <div className="mt-6 space-y-4" aria-busy="true">
          <Skeleton className="h-56" />
          <Skeleton className="h-56" />
        </div>
      ) : null}

      {data && !error ? (
        <div className="mt-6 space-y-6">
          <p className="text-sm text-ink-700" aria-live="polite">
            {data.recommendations.length === 0
              ? "No rule triggered on this selection."
              : `${data.recommendations.length} recommendation(s) from ${fired.length} of ${data.rules.length} rules checked.`}{" "}
            Scope: {data.scope.label}. Look-back window: {data.window_days} days to {formatDate(data.as_of)}.
          </p>

          {data.recommendations.length === 0 ? (
            <Card>
              <EmptyState title="No action is recommended on the current evidence.">
                See the rules checked below for what was tested.
              </EmptyState>
            </Card>
          ) : (
            <div className="space-y-5">
              {data.recommendations.map((item) => (
                <RecommendationCard key={item.id} item={item} />
              ))}
            </div>
          )}

          <Card labelledBy="rules-title">
            <CardHeader
              id="rules-title"
              title="Rules checked"
              description="Every rule, whether or not it fired, with the reason and the numbers it used."
            />
            <div className="overflow-x-auto p-5">
              <table className="w-full min-w-[640px] text-left text-sm">
                <caption className="sr-only">Recommendation rules and outcomes</caption>
                <thead className="bg-slate-100 text-xs uppercase tracking-wide text-ink-700">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-semibold">Rule</th>
                    <th scope="col" className="px-3 py-2 font-semibold">Outcome</th>
                    <th scope="col" className="px-3 py-2 font-semibold">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {[...fired, ...notFired].map((rule) => (
                    <tr key={rule.rule_id} className="border-t border-line align-top">
                      <td className="px-3 py-2 font-medium text-ink-900">{rule.title}</td>
                      <td className="px-3 py-2">
                        <span className={rule.fired ? "font-semibold text-brick-700" : "text-ink-500"}>
                          {rule.fired ? "Triggered" : "Not triggered"}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-ink-700">{rule.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card labelledBy="rec-notes-title">
            <CardHeader id="rec-notes-title" title="How to read these" />
            <ul className="list-disc space-y-2 p-5 pl-9 text-sm text-ink-700">
              {data.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
              <li>
                Thresholds are policy choices listed in the backend policy module. They are not learned from data.{" "}
                <Link href="/forecast" className="font-medium text-forest-800 underline">
                  Check the forecast
                </Link>{" "}
                behind the forecast-based rules.
              </li>
            </ul>
          </Card>
        </div>
      ) : null}
    </>
  );
}
