import { SourceBadge } from "@/components/ui/Badges";
import { Card, CardHeader } from "@/components/ui/Card";
import { StatusPill, type Tone } from "@/components/ui/Badges";
import { formatDate, formatNumber } from "@/lib/format";
import type { OverviewResponse } from "@/lib/types";

const FRESHNESS_TONE: Record<string, Tone> = {
  fresh: "good",
  stale: "warn",
  unknown: "neutral",
};

export function FreshnessCard({ data }: { data: OverviewResponse }) {
  const { freshness, period, provenance, dataset } = data;
  const tone = FRESHNESS_TONE[freshness.status] ?? "neutral";
  const statusText =
    freshness.status === "fresh"
      ? "Fresh"
      : freshness.status === "stale"
        ? "Stale"
        : "No actuals recorded";
  return (
    <Card labelledBy="freshness-title" className="h-full">
      <CardHeader id="freshness-title" title="Data freshness and provenance" />
      <div className="space-y-4 p-5 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone={tone}>{statusText}</StatusPill>
          <SourceBadge sourceType={dataset.source_type} />
        </div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
          <div>
            <dt className="text-xs text-ink-500">Last actual recorded</dt>
            <dd className="font-medium text-ink-900">{formatDate(freshness.last_actual_date)}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-500">Days since (as of {formatDate(freshness.as_of)})</dt>
            <dd className="font-medium text-ink-900">
              {freshness.days_since_last_actual === null ? "n/a" : formatNumber(freshness.days_since_last_actual)}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-ink-500">Rows in selection</dt>
            <dd className="font-medium text-ink-900">{formatNumber(period.rows)}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-500">Rows pending an actual</dt>
            <dd className="font-medium text-ink-900">{formatNumber(period.rows_pending_actual)}</dd>
          </div>
        </dl>
        <div>
          <p className="text-xs font-medium text-ink-700">Source</p>
          <p className="mt-1 text-ink-700">{provenance.provider}</p>
          <p className="mt-1 text-xs text-ink-500">{provenance.description}</p>
        </div>
        {provenance.limitations.length > 0 ? (
          <details className="rounded border border-line bg-slate-100/60 p-3">
            <summary className="cursor-pointer font-medium text-ink-900">
              Limitations ({provenance.limitations.length})
            </summary>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-ink-700">
              {provenance.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </details>
        ) : null}
      </div>
    </Card>
  );
}
