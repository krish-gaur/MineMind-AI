"use client";

import Link from "next/link";
import { useState } from "react";
import { BandCard } from "@/components/risk/BandCard";
import { SyntheticBanner } from "@/components/data/SyntheticBanner";
import { PageHeader } from "@/components/layout/PageHeader";
import { ScopeFilters } from "@/components/scope/ScopeFilters";
import { ValueKindBadge, StatusPill } from "@/components/ui/Badges";
import { Card, CardHeader } from "@/components/ui/Card";
import { KpiCard } from "@/components/ui/Kpi";
import { EmptyState, ErrorState, LoadingBlock, Skeleton } from "@/components/ui/States";
import { useDatasets } from "@/lib/dataset-context";
import {
  formatDate,
  formatNumber,
  formatPercent,
  formatSignedPercent,
  formatSignedTonnes,
  formatTonnes,
} from "@/lib/format";
import type { DatasetSummary, RiskResponse } from "@/lib/types";
import { useApiResource } from "@/lib/useApiResource";

export default function RiskPage() {
  const { active, datasets, datasetsError, reloadDatasets } = useDatasets();
  if (datasetsError) {
    return (
      <>
        <PageHeader title="Shortfall risk" />
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
        <PageHeader title="Shortfall risk" />
        <Card>
          <EmptyState title="No production dataset is available yet." />
        </Card>
      </>
    );
  }
  return <RiskView key={active.id} dataset={active} />;
}

function RiskView({ dataset }: { dataset: DatasetSummary }) {
  const [mineId, setMineId] = useState("");
  const [zoneId, setZoneId] = useState("");
  const [horizon, setHorizon] = useState(30);
  const params = { dataset_id: dataset.id, mine_id: mineId, zone_id: zoneId, horizon_days: horizon };
  const { data, error, loading, refreshing, reload } = useApiResource<RiskResponse>("/api/risk", params);

  return (
    <>
      <PageHeader
        title="Shortfall risk"
        description="How far output is expected to fall below plan over the horizon, how likely a shortfall is, and the rule that sets the risk band."
        status={
          <span aria-live="polite" className="text-xs text-ink-500">
            {refreshing ? "Updating..." : data ? `Scope: ${data.scope.label}` : ""}
          </span>
        }
      />
      {dataset.is_synthetic ? <SyntheticBanner text="Risk bands computed from synthetic data illustrate the rule. They do not describe MOIL risk." /> : null}
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
            <ErrorState error={error} onRetry={reload} />
          </Card>
        </div>
      ) : null}
      {loading && !error ? (
        <div className="mt-6 space-y-6" aria-busy="true">
          <Skeleton className="h-36" />
          <Skeleton className="h-48" />
        </div>
      ) : null}

      {data && !error ? <RiskContent data={data} /> : null}
    </>
  );
}

function RiskContent({ data }: { data: RiskResponse }) {
  const expected = data.expected;
  const probability = data.shortfall_probability;
  const check = data.classification_check;
  return (
    <div className="mt-6 space-y-6">
      <BandCard band={data.band} />

      {expected ? (
        <section aria-label="Expected shortfall" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard label="Planned" value={formatTonnes(expected.plan_t)} hint={`${data.horizon.start} to ${data.horizon.end}`} valueKind="measured" />
          <KpiCard label="Forecast output" value={formatTonnes(expected.forecast_t)} hint="Model output" valueKind="forecast" />
          <KpiCard
            label="Expected net gap"
            value={formatSignedTonnes(expected.net_gap_t)}
            hint={`${formatSignedPercent(expected.net_gap_pct)} of plan`}
            tone={expected.net_gap_t < 0 ? "bad" : "good"}
            valueKind="estimate"
          />
          <KpiCard
            label="Gap range (approx. P10 to P90)"
            value={
              expected.gap_interval_low_t === null || expected.gap_interval_high_t === null
                ? "n/a"
                : `${formatNumber(expected.gap_interval_low_t)} to ${formatNumber(expected.gap_interval_high_t)} t`
            }
            hint="Empirical from backtest"
            valueKind="estimate"
          />
        </section>
      ) : (
        <Card>
          <EmptyState title="No risk estimate is available.">
            {data.limitations.map((item) => (
              <span key={item} className="block">
                {item}
              </span>
            ))}
          </EmptyState>
        </Card>
      )}

      <div className="grid gap-6 xl:grid-cols-2">
        <Card labelledBy="probability-title">
          <CardHeader
            id="probability-title"
            title="How likely is a shortfall?"
            description="Two different probabilities: one for the whole horizon, one for a single day."
          />
          <div className="space-y-5 p-5 text-sm">
            <div>
              <p className="text-xs text-ink-500">Probability the period ends below plan</p>
              <p className="tabular mt-1 font-mono text-2xl font-semibold text-ink-900">
                {probability?.period_probability === null || probability === null
                  ? "n/a"
                  : formatPercent((probability.period_probability ?? 0) * 100, 0)}
              </p>
              <p className="mt-1 text-xs text-ink-500">{probability?.period_basis}</p>
              <ValueKindBadge kind="probability" />
            </div>
            <div className="border-t border-line pt-4">
              <p className="text-xs text-ink-500">Average daily probability of a material shortfall</p>
              <p className="tabular mt-1 font-mono text-2xl font-semibold text-ink-900">
                {probability ? formatPercent(probability.mean_daily_probability * 100, 0) : "n/a"}
              </p>
              <p className="mt-1 text-xs text-ink-500">{probability?.daily_definition}</p>
              <ValueKindBadge kind="probability" />
            </div>
          </div>
        </Card>

        <Card labelledBy="check-title">
          <CardHeader
            id="check-title"
            title="Do the models beat simple baselines?"
            description="These checks come from the backtest, not from the forecast horizon."
          />
          <div className="space-y-4 p-5 text-sm">
            {check ? (
              <>
                <StatusPill tone={check.verdict === "beats_base_rate" ? "good" : check.verdict === "not_evaluable" ? "neutral" : "warn"}>
                  {check.verdict.replaceAll("_", " ")}
                </StatusPill>
                <p className="text-ink-900">{check.text}</p>
              </>
            ) : null}
            {data.model_check ? (
              <p className="text-ink-700">
                Regression: <span className="font-medium">{data.model_check.regression_text}</span>
              </p>
            ) : null}
            <p className="text-xs text-ink-500">
              Classifier n = {check ? formatNumber(check.n) : "n/a"}, base rate{" "}
              {check ? formatPercent(check.base_rate * 100, 0) : "n/a"}.
            </p>
          </div>
        </Card>
      </div>

      <Card labelledBy="risk-drivers-title">
        <CardHeader
          id="risk-drivers-title"
          title="Drivers of the forecast"
          description="Permutation importance on the last backtest fold. Shows reliance, not cause."
        />
        {data.drivers.length === 0 ? (
          <div className="p-5">
            <EmptyState title="No driver analysis is available." />
          </div>
        ) : (
          <ol className="grid gap-x-8 gap-y-2 p-5 text-sm md:grid-cols-2">
            {data.drivers.map((driver) => (
              <li key={driver.feature} className="flex justify-between gap-3 border-b border-line pb-2">
                <span>{driver.label}</span>
                <span className="tabular font-mono text-xs text-ink-700">+{formatNumber(driver.importance_t, 1)} t MAE</span>
              </li>
            ))}
          </ol>
        )}
      </Card>

      <Card labelledBy="risk-limits-title">
        <CardHeader id="risk-limits-title" title="Limitations" />
        <ul className="list-disc space-y-2 p-5 pl-9 text-sm text-ink-700">
          {data.limitations.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <div className="flex flex-wrap gap-4 border-t border-line px-5 py-4 text-sm">
          <Link href="/forecast" className="font-medium text-forest-800 underline">
            See the forecast and backtest
          </Link>
          <Link href="/recommendations" className="font-medium text-forest-800 underline">
            See recommended actions
          </Link>
          {data.horizon.start ? (
            <span className="text-xs text-ink-500">
              Horizon {formatDate(data.horizon.start)} to {formatDate(data.horizon.end)}
            </span>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
