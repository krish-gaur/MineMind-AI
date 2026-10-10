import { ValueKindBadge } from "@/components/ui/Badges";
import { formatSignedPercent } from "@/lib/format";
import type { RiskResponse } from "@/lib/types";

const BAND_STYLE: Record<RiskResponse["band"]["level"], { classes: string; label: string }> = {
  high: { classes: "border-brick-500 bg-brick-100 text-brick-800", label: "HIGH" },
  medium: { classes: "border-amber-500 bg-amber-100 text-amber-900", label: "MEDIUM" },
  low: { classes: "border-forest-500 bg-forest-50 text-forest-800", label: "LOW" },
  insufficient_data: { classes: "border-line-strong bg-slate-100 text-ink-700", label: "NOT ASSESSED" },
};

export function BandCard({ band }: { band: RiskResponse["band"] }) {
  const style = BAND_STYLE[band.level];
  return (
    <section aria-labelledby="band-title" className="rounded-lg border border-line bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 id="band-title" className="text-xs font-semibold uppercase tracking-wide text-ink-500">
            Shortfall risk band
          </h2>
          <p
            data-testid="risk-band"
            className={`mt-2 inline-flex items-center rounded-md border-2 px-4 py-2 text-xl font-bold tracking-wide ${style.classes}`}
          >
            {style.label}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <ValueKindBadge kind="rule_based" />
          <p className="text-xs text-ink-500">
            Expected net gap:{" "}
            <span className="tabular font-mono text-ink-900">{formatSignedPercent(band.expected_net_gap_pct)}</span>
          </p>
        </div>
      </div>
      <p className="mt-4 text-sm text-ink-700">{band.rule}</p>
    </section>
  );
}
