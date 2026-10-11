import { StatusPill, type Tone, ValueKindBadge } from "@/components/ui/Badges";
import { formatNumber } from "@/lib/format";
import type { RecommendationItem } from "@/lib/types";

const PRIORITY: Record<RecommendationItem["priority"], { label: string; tone: Tone }> = {
  high: { label: "High priority", tone: "bad" },
  medium: { label: "Medium priority", tone: "warn" },
  low: { label: "Low priority", tone: "neutral" },
};

const CATEGORY_LABEL: Record<string, string> = {
  maintenance: "Maintenance",
  production: "Production",
  planning: "Planning",
  drilling_blasting: "Drilling and blasting",
  data: "Data",
  model: "Model reliability",
};

export function RecommendationCard({ item }: { item: RecommendationItem }) {
  const priority = PRIORITY[item.priority];
  const impact = item.expected_impact;
  return (
    <article aria-labelledby={`${item.id}-title`} className="rounded-lg border border-line bg-surface">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill tone={priority.tone}>{priority.label}</StatusPill>
            <span className="rounded border border-line px-2 py-0.5 text-xs text-ink-700">
              {CATEGORY_LABEL[item.category] ?? item.category}
            </span>
            {item.zone_id ? (
              <span className="rounded border border-line px-2 py-0.5 font-mono text-xs text-ink-700">{item.zone_id}</span>
            ) : null}
            <ValueKindBadge kind="rule_based" />
          </div>
          <h3 id={`${item.id}-title`} className="mt-2 text-base font-semibold text-ink-900">
            {item.title}
          </h3>
          <p className="mt-1 text-sm text-ink-700">{item.summary}</p>
        </div>
        <p className="shrink-0 font-mono text-[11px] text-ink-500">{item.id}</p>
      </header>

      <div className="grid gap-6 p-5 lg:grid-cols-5">
        <div className="space-y-4 lg:col-span-3">
          <p className="text-sm text-ink-700">{item.reasoning}</p>
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-500">Evidence</h4>
            <table className="mt-2 w-full text-left text-xs">
              <caption className="sr-only">Evidence for {item.title}</caption>
              <thead className="text-ink-500">
                <tr>
                  <th scope="col" className="py-1 pr-3 font-medium">Metric</th>
                  <th scope="col" className="py-1 pr-3 text-right font-medium">Value</th>
                  <th scope="col" className="py-1 pr-3 font-medium">Period</th>
                  <th scope="col" className="py-1 font-medium">Value type</th>
                </tr>
              </thead>
              <tbody>
                {item.evidence.map((evidence, index) => (
                  <tr key={`${evidence.metric}-${index}`} className="border-t border-line">
                    <td className="py-1.5 pr-3">{evidence.metric}</td>
                    <td className="tabular py-1.5 pr-3 text-right font-mono">
                      {typeof evidence.value === "number" ? formatNumber(evidence.value, Math.abs(evidence.value) < 10 ? 2 : 0) : evidence.value ?? "n/a"}{" "}
                      <span className="text-ink-500">{evidence.unit}</span>
                    </td>
                    <td className="py-1.5 pr-3 text-ink-700">{evidence.period}</td>
                    <td className="py-1.5 text-ink-700">{evidence.value_kind}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-500">Suggested actions</h4>
            <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-sm text-ink-900">
              {item.suggested_actions.map((action) => (
                <li key={action}>{action}</li>
              ))}
            </ol>
          </div>
        </div>

        <aside className="space-y-4 rounded-md border border-line bg-slate-100/60 p-4 text-sm lg:col-span-2" aria-label="Impact and confidence">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">Expected impact</p>
            {impact.status === "estimated" ? (
              <p className="mt-1">
                <span className="tabular font-mono text-lg font-semibold text-ink-900">
                  {impact.value_t === null ? "n/a" : `${formatNumber(impact.value_t)} ${impact.unit}`}
                </span>
                <span className="ml-2 rounded border border-amber-500 bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium text-amber-900">
                  ESTIMATED
                </span>
              </p>
            ) : (
              <p className="mt-1 font-medium text-ink-900">
                Not estimated <span className="ml-1 text-xs font-normal text-ink-500">(insufficient basis)</span>
              </p>
            )}
            <p className="mt-2 text-xs text-ink-700">{impact.basis}</p>
          </div>
          <div className="border-t border-line pt-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">
              Confidence: <span className="text-ink-900">{item.confidence.level}</span>
            </p>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-ink-700">
              {item.confidence.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>
          {item.limitations.length > 0 ? (
            <div className="border-t border-line pt-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">Limitations</p>
              <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-ink-700">
                {item.limitations.map((limit) => (
                  <li key={limit}>{limit}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </aside>
      </div>
    </article>
  );
}
