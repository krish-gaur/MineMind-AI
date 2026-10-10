"use client";

import Link from "next/link";
import { useState } from "react";
import { BacktestChart, ForwardChart } from "@/components/forecast/ForecastCharts";
import {
  ClassificationSection,
  DriversSection,
  EvaluationSection,
  ModelCardSection,
  ModelComparisonSection,
} from "@/components/forecast/ForecastSections";
import { SyntheticBanner } from "@/components/data/SyntheticBanner";
import { PageHeader } from "@/components/layout/PageHeader";
import { ScopeFilters } from "@/components/scope/ScopeFilters";
import { Card, CardHeader } from "@/components/ui/Card";
import { KpiCard } from "@/components/ui/Kpi";
import { ValueKindBadge } from "@/components/ui/Badges";
import { EmptyState, ErrorState, LoadingBlock, Skeleton } from "@/components/ui/States";
import { ApiError } from "@/lib/api";
import { useDatasets } from "@/lib/dataset-context";
import {
  formatDate,
  formatNumber,
  formatPercent,
  formatSignedPercent,
  formatSignedTonnes,
  formatTonnes,
} from "@/lib/format";
import type { DatasetSummary, ForecastResponse } from "@/lib/types";
import { useApiResource } from "@/lib/useApiResource";

export default function ForecastPage() {
  const { active, datasets, datasetsError, reloadDatasets } = useDatasets();
  if (datasetsError) {
    return (
      <>
        <PageHeader title="Production forecast" />
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
        <PageHeader title="Production forecast" />
        <Card>
          <EmptyState title="No production dataset is available yet.">
            <Link href="/data" className="font-medium text-forest-800 underline">
              Upload production records
            </Link>
          </EmptyState>
        </Card>
      </>
    );
  }
  return <ForecastView key={active.id} dataset={active} />;
}

function ForecastView({ dataset }: { dataset: DatasetSummary }) {
  const [mineId, setMineId] = useState("");
  const [zoneId, setZoneId] = useState("");
  const [horizon, setHorizon] = useState(30);
  const params = { dataset_id: dataset.id, mine_id: mineId, zone_id: zoneId, horizon_days: horizon };
  const { data, error, loading, refreshing, reload } = useApiResource<ForecastResponse>("/api/forecast", params);
  const totals = data?.forecast.totals ?? null;

  return (
    <>
      <PageHeader
        title="Production forecast"
        description="Daily output forecast from a time-ordered backtest. Every model is compared with simple baselines on the same days, and the forecast is labelled as a model output."
        status={
          <span aria-live="polite" className="text-xs text-ink-500">
            {refreshing ? "Updating..." : data ? `Scope: ${data.scope.label}` : ""}
          </span>
        }
      />
      {dataset.is_synthetic ? <SyntheticBanner text="Forecasts from synthetic data show how the method behaves. They say nothing about MOIL operations." /> : null}

      <div className="mt-5">
        <ScopeFilters
          dataset={dataset}
          mineId={mineId}
          zoneId={zoneId}
          onMine={setMineId}
          onZone={setZoneId}
          horizon={horizon}
          onHorizon={setHorizon}
        />
      </div>

      {error ? (
        <div className="mt-5">
          <Card>
            <ErrorState
              error={error}
              onRetry={reload}
              title={error instanceof ApiError && error.code === "insufficient_data" ? "Not enough data to forecast this scope" : undefined}
            />
          </Card>
        </div>
      ) : null}

      {loading && !error ? (
        <div className="mt-6 space-y-6" aria-busy="true">
          <Skeleton className="h-40" />
          <Skeleton className="h-64" />
          <Skeleton className="h-96" />
        </div>
      ) : null}

      {data && !error ? (
        <div className="mt-6 space-y-6">
          <section aria-label="Forecast headline" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              label="Forecast output"
              value={formatTonnes(totals?.forecast_t ?? null)}
              hint={totals ? `${totals.start} to ${totals.end}` : "No horizon"}
              valueKind="forecast"
            />
            <KpiCard
              label="Planned tonnes"
              value={formatTonnes(totals?.plan_t ?? null)}
              hint={`${data.forecast.forecast_days} days`}
              valueKind="measured"
            />
            <KpiCard
              label="Expected net gap"
              value={formatSignedTonnes(totals?.net_gap_t ?? null)}
              hint={`${formatSignedPercent(totals?.net_gap_pct ?? null)} of plan`}
              tone={totals && totals.net_gap_t < 0 ? "bad" : "good"}
              valueKind="estimate"
            />
            <KpiCard
              label="Backtest skill vs best baseline"
              value={
                data.evaluation.gap_to_best_baseline.skill_pct_vs_best_baseline === null
                  ? "n/a"
                  : formatPercent(data.evaluation.gap_to_best_baseline.skill_pct_vs_best_baseline, 1)
              }
              hint={`${formatNumber(data.evaluation.n_evaluated_days)} out-of-sample days`}
              tone={data.evaluation.verdict === "beats_best_baseline" ? "good" : "warn"}
              valueKind="estimate"
            />
          </section>

          <ModelCardSection model={data.model} dataset={data.dataset} />
          <EvaluationSection evaluation={data.evaluation} />
          <ModelComparisonSection evaluation={data.evaluation} />

          <Card labelledBy="backtest-title">
            <CardHeader
              id="backtest-title"
              title="Backtest: forecast against actual"
              description="Out-of-sample predictions for the last backtest period. Each day is predicted using only earlier information."
              actions={<ValueKindBadge kind="forecast" />}
            />
            <div className="p-5">
              {data.backtest_history.length === 0 ? (
                <EmptyState title="No backtest days to show." />
              ) : (
                <BacktestChart history={data.backtest_history} />
              )}
            </div>
          </Card>

          <Card labelledBy="forward-title">
            <CardHeader
              id="forward-title"
              title="Forward forecast"
              description={`Next ${data.forecast.forecast_days} day(s) after the last recorded actual. Operational inputs are scenario assumptions.`}
              actions={<ValueKindBadge kind="scenario" />}
            />
            <div className="space-y-5 p-5">
              {data.forecast.truncated_reason ? (
                <p role="note" className="rounded-md border border-amber-500 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  {data.forecast.truncated_reason}
                </p>
              ) : null}
              {data.forecast.days.length === 0 ? (
                <EmptyState title="No forecast days could be produced." />
              ) : (
                <ForwardChart days={data.forecast.days} />
              )}
              {totals ? (
                <dl className="grid gap-4 rounded-md border border-line bg-slate-100/60 p-4 text-sm sm:grid-cols-2 xl:grid-cols-4">
                  <div>
                    <dt className="text-xs text-ink-500">Gap interval (approx. 10th to 90th percentile)</dt>
                    <dd className="tabular font-mono">
                      {totals.gap_interval_low_t === null || totals.gap_interval_high_t === null
                        ? "not estimated"
                        : `${formatSignedTonnes(totals.gap_interval_low_t)} to ${formatSignedTonnes(totals.gap_interval_high_t)}`}
                    </dd>
                    <dd className="mt-1 text-xs text-ink-500">{totals.interval_basis}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-ink-500">Probability the period ends below plan</dt>
                    <dd className="tabular font-mono">
                      {totals.period_shortfall_probability === null
                        ? "not estimated"
                        : formatPercent(totals.period_shortfall_probability * 100, 0)}
                    </dd>
                    <dd className="mt-1 text-xs text-ink-500">Empirical, from backtest windows.</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-ink-500">Mean daily probability of a material shortfall</dt>
                    <dd className="tabular font-mono">{formatPercent(totals.mean_daily_shortfall_probability * 100, 0)}</dd>
                    <dd className="mt-1 text-xs text-ink-500">Classifier output (probability).</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-ink-500">Scenario inputs held at trailing means</dt>
                    <dd className="text-xs text-ink-700">
                      {Object.entries(data.forecast.scenario_assumptions.values)
                        .map(([key, value]) => `${key.replaceAll("_", " ")} ${formatNumber(value, 2)}`)
                        .join("; ") || "none"}
                    </dd>
                    <dd className="mt-1 text-xs text-ink-500">{data.forecast.scenario_assumptions.description}</dd>
                  </div>
                </dl>
              ) : null}
              {data.forecast.days.length > 0 ? (
                <p className="text-xs text-ink-500">
                  Forecast dates: {formatDate(data.forecast.days[0]?.date)} to {formatDate(data.forecast.days.at(-1)?.date)}.
                </p>
              ) : null}
            </div>
          </Card>

          <ClassificationSection classification={data.classification} />
          <DriversSection drivers={data.drivers} />

          <Card labelledBy="notes-title">
            <CardHeader id="notes-title" title="Notes and limitations" />
            <ul className="list-disc space-y-2 p-5 pl-9 text-sm text-ink-700">
              {data.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </Card>
        </div>
      ) : null}
    </>
  );
}
