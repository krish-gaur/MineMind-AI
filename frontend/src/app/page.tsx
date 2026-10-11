"use client";

import Link from "next/link";
import { useState } from "react";
import { FreshnessCard } from "@/components/overview/FreshnessCard";
import { ConstraintBreakdown } from "@/components/overview/ConstraintBreakdown";
import { MonthlyTrendChart } from "@/components/overview/MonthlyTrendChart";
import { OverviewFilters, type RangePreset, resolveRange } from "@/components/overview/OverviewFilters";
import { ZoneTable } from "@/components/overview/ZoneTable";
import { SyntheticBanner } from "@/components/data/SyntheticBanner";
import { Card, CardHeader } from "@/components/ui/Card";
import { KpiCard } from "@/components/ui/Kpi";
import { EmptyState, ErrorState, LoadingBlock, Skeleton } from "@/components/ui/States";
import { PageHeader } from "@/components/layout/PageHeader";
import { ApiError } from "@/lib/api";
import { useDatasets } from "@/lib/dataset-context";
import {
  formatDate,
  formatHours,
  formatNumber,
  formatPercent,
  formatSignedPercent,
  formatSignedTonnes,
  formatTonnes,
} from "@/lib/format";
import { ATTAINMENT_TARGET_PCT, DOWNTIME_HEAVY_DAY_H } from "@/lib/labels";
import type { DatasetSummary, OverviewResponse } from "@/lib/types";
import { useApiResource } from "@/lib/useApiResource";

export default function OverviewPage() {
  const { active, datasets, datasetsError, reloadDatasets } = useDatasets();

  if (datasetsError) {
    return (
      <>
        <PageHeader title="Executive overview" />
        <Card>
          <ErrorState error={datasetsError} onRetry={reloadDatasets} title="Datasets could not be loaded" />
        </Card>
      </>
    );
  }
  if (datasets === null) {
    return (
      <>
        <PageHeader title="Executive overview" />
        <Card>
          <LoadingBlock label="Loading datasets" />
        </Card>
      </>
    );
  }
  if (active === null) {
    return (
      <>
        <PageHeader title="Executive overview" />
        <Card>
          <EmptyState
            title="No production dataset is available yet."
            action={
              <Link href="/data" className="font-medium text-forest-800 underline">
                Upload production records
              </Link>
            }
          />
        </Card>
      </>
    );
  }
  return <OverviewView key={active.id} dataset={active} />;
}

function attainmentTone(value: number | null): "good" | "warn" | "bad" | "neutral" {
  if (value === null) return "neutral";
  if (value >= 100) return "good";
  if (value >= ATTAINMENT_TARGET_PCT) return "warn";
  return "bad";
}

function OverviewView({ dataset }: { dataset: DatasetSummary }) {
  const [preset, setPreset] = useState<RangePreset>("365d");
  const [custom, setCustom] = useState({ start: "", end: "" });
  const [mineId, setMineId] = useState("");
  const [zoneId, setZoneId] = useState("");
  const range = resolveRange(preset, dataset, custom);
  const params = {
    dataset_id: dataset.id,
    start: range.start,
    end: range.end,
    mine_id: mineId,
    zone_id: zoneId,
  };
  const { data, error, loading, refreshing, reload } = useApiResource<OverviewResponse>("/api/overview", params);

  return (
    <>
      <PageHeader
        title="Executive overview"
        description="Plan against actual production, the constraints behind any gap, and how fresh the data is. Gap and attainment use matched days only."
        status={
          <span aria-live="polite" className="text-xs text-ink-500">
            {refreshing ? "Updating..." : data ? `Data as of ${formatDate(data.freshness.as_of)}` : ""}
          </span>
        }
      />

      {dataset.is_synthetic ? <SyntheticBanner /> : null}

      <div className="mt-5">
        <OverviewFilters
          dataset={dataset}
          preset={preset}
          onPreset={setPreset}
          custom={custom}
          onCustom={setCustom}
          mineId={mineId}
          onMine={setMineId}
          zoneId={zoneId}
          onZone={setZoneId}
        />
      </div>

      {error ? (
        <div className="mt-5">
          <Card>
            <ErrorState
              error={error}
              onRetry={reload}
              title={
                error instanceof ApiError && error.status === 422
                  ? "This selection is not valid"
                  : "The overview could not be loaded"
              }
            />
          </Card>
        </div>
      ) : null}

      {loading && !error ? <OverviewSkeleton /> : null}

      {data && !error ? <OverviewContent data={data} /> : null}
    </>
  );
}

function OverviewSkeleton() {
  return (
    <div className="mt-6 space-y-6" aria-busy="true">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, index) => (
          <Skeleton key={index} className="h-28" />
        ))}
      </div>
      <Skeleton className="h-80" />
    </div>
  );
}

function OverviewContent({ data }: { data: OverviewResponse }) {
  const { kpis, period, constraints, monthly, zones, freshness } = data;
  const gapTone = kpis.gap_t === null ? "neutral" : kpis.gap_t < 0 ? "bad" : "good";
  const downtimeTone =
    kpis.equipment_downtime_h_per_zone_day === null
      ? "neutral"
      : kpis.equipment_downtime_h_per_zone_day > DOWNTIME_HEAVY_DAY_H / 2
        ? "warn"
        : "neutral";

  return (
    <div className="mt-6 space-y-6">
      {/* The synthetic warning is already shown as a banner above; do not repeat it here. */}
      {data.notes.filter((note) => !note.startsWith("SYNTHETIC DEMONSTRATION DATA")).length > 0 ? (
        <ul className="space-y-2 text-sm text-ink-700" aria-label="Notes on this view">
          {data.notes
            .filter((note) => !note.startsWith("SYNTHETIC DEMONSTRATION DATA"))
            .map((note) => (
              <li key={note} className="rounded-md border border-line bg-surface px-4 py-2.5">
                {note}
              </li>
            ))}
        </ul>
      ) : null}

      {data.empty ? (
        <Card>
          <EmptyState title="No records match these filters.">
            Widen the date range, or choose &quot;All mines&quot; and &quot;All zones&quot;.
          </EmptyState>
        </Card>
      ) : null}

      <section aria-label="Key figures" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <KpiCard
          label="Planned (matched days)"
          value={formatTonnes(kpis.planned_t)}
          hint={`${formatNumber(period.rows_with_actual)} of ${formatNumber(period.rows)} rows`}
          valueKind="measured"
          testId="kpi-planned"
        />
        <KpiCard
          label="Actual"
          value={formatTonnes(kpis.actual_t)}
          hint={`Coverage ${formatPercent(kpis.coverage_pct, 1)}`}
          valueKind="measured"
          testId="kpi-actual"
        />
        <KpiCard
          label="Gap to plan"
          value={formatSignedTonnes(kpis.gap_t)}
          hint={`Variance ${formatSignedPercent(kpis.variance_pct)}`}
          tone={gapTone}
          valueKind="estimate"
          testId="kpi-gap"
        />
        <KpiCard
          label="Attainment"
          value={formatPercent(kpis.attainment_pct)}
          hint={`Target ${ATTAINMENT_TARGET_PCT}% (policy)`}
          tone={attainmentTone(kpis.attainment_pct)}
          valueKind="estimate"
          testId="kpi-attainment"
        />
        <KpiCard
          label="Equipment downtime"
          value={formatHours(kpis.equipment_downtime_h_per_zone_day, 2)}
          hint="Mean per zone-day"
          tone={downtimeTone}
          valueKind="measured"
          testId="kpi-downtime"
        />
        <KpiCard
          label="Days below plan"
          value={formatPercent(kpis.days_below_plan_pct)}
          hint={`${formatPercent(kpis.equipment_downtime_days_over_threshold_pct)} of zone-days over ${DOWNTIME_HEAVY_DAY_H} h downtime`}
          valueKind="measured"
          testId="kpi-days-below"
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-5">
        <Card labelledBy="trend-title" className="xl:col-span-3">
          <CardHeader
            id="trend-title"
            title="Monthly plan and actual"
            description="Tonnes per month on matched days, with attainment on the right-hand axis."
          />
          <div className="p-5">
            {monthly.length === 0 ? (
              <EmptyState title="No matched days in this selection." />
            ) : (
              <MonthlyTrendChart points={monthly} />
            )}
          </div>
        </Card>

        <Card labelledBy="constraints-title" className="xl:col-span-2">
          <CardHeader
            id="constraints-title"
            title="Where hours were lost"
            description="Recorded delay hours by cause, across all zone-days in the selection."
          />
          <div className="p-5">
            {constraints.length === 0 || constraints.every((item) => item.records === 0) ? (
              <EmptyState title="No delay hours were recorded in this selection." />
            ) : (
              <ConstraintBreakdown items={constraints} />
            )}
          </div>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-5">
        <Card labelledBy="zones-title" className="xl:col-span-3">
          <CardHeader
            id="zones-title"
            title="Mine and zone performance"
            description="Sorted by gap to plan, largest shortfall first."
          />
          {zones.length === 0 ? (
            <div className="p-5">
              <EmptyState title="No zones match these filters." />
            </div>
          ) : (
            <ZoneTable zones={zones} />
          )}
        </Card>
        <div className="xl:col-span-2">
          <FreshnessCard data={data} />
        </div>
      </div>

      {freshness.status === "stale" ? (
        <p className="text-sm text-amber-900">
          The latest actual is older than the {freshness.stale_threshold_days}-day freshness threshold. Figures
          describe the period shown, not current operations.
        </p>
      ) : null}
    </div>
  );
}
