import { ValueKindBadge } from "@/components/ui/Badges";
import { formatHours, formatPercent } from "@/lib/format";
import type { ConstraintItem } from "@/lib/types";

/** Horizontal bars of lost hours by cause. Plain HTML so it reads well to assistive tech. */
export function ConstraintBreakdown({ items }: { items: ConstraintItem[] }) {
  const largest = Math.max(1, ...items.map((item) => item.total_hours ?? 0));
  return (
    <ul className="space-y-4">
      {items.map((item) => {
        const width = ((item.total_hours ?? 0) / largest) * 100;
        return (
          <li key={item.key}>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="text-sm font-medium text-ink-900">{item.label}</p>
              <p className="tabular font-mono text-sm text-ink-900">
                {formatHours(item.total_hours, 0)}
                <span className="ml-2 text-xs text-ink-500">{formatPercent(item.share_pct, 1)} of hours lost</span>
              </p>
            </div>
            <div
              className="mt-1.5 h-2.5 w-full overflow-hidden rounded-full bg-slate-100"
              role="img"
              aria-label={`${item.label}: ${formatHours(item.total_hours, 0)}, ${formatPercent(item.share_pct, 1)} of hours lost`}
            >
              <div className="h-full rounded-full bg-amber-500" style={{ width: `${width}%` }} />
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-ink-500">
              <span>
                Mean {formatHours(item.mean_hours_per_zone_day, 2)} per zone-day · {item.days_over_threshold} heavy
                day(s) above {formatHours(item.threshold_hours, 0)}
              </span>
              <ValueKindBadge kind={item.value_kind} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
