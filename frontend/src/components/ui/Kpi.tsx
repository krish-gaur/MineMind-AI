import { ValueKindBadge } from "./Badges";
import type { ValueKind } from "@/lib/types";

type Tone = "neutral" | "good" | "bad" | "warn";

const ACCENT: Record<Tone, string> = {
  neutral: "bg-line-strong",
  good: "bg-forest-500",
  bad: "bg-brick-500",
  warn: "bg-amber-500",
};

const VALUE_TONE: Record<Tone, string> = {
  neutral: "text-ink-900",
  good: "text-forest-800",
  bad: "text-brick-700",
  warn: "text-amber-900",
};

type KpiProps = {
  label: string;
  value: string;
  hint?: string;
  tone?: Tone;
  valueKind?: ValueKind;
  testId?: string;
};

export function KpiCard({ label, value, hint, tone = "neutral", valueKind, testId }: KpiProps) {
  return (
    <div
      data-testid={testId}
      className="relative overflow-hidden rounded-lg border border-line bg-surface p-4 pl-5"
    >
      <span aria-hidden="true" className={`absolute inset-y-0 left-0 w-1 ${ACCENT[tone]}`} />
      <p className="text-xs font-medium uppercase tracking-wide text-ink-500">{label}</p>
      <p className={`tabular mt-2 font-mono text-2xl font-semibold ${VALUE_TONE[tone]}`}>{value}</p>
      <div className="mt-2 flex min-h-5 flex-wrap items-center gap-2">
        {hint ? <span className="text-xs text-ink-500">{hint}</span> : null}
        {valueKind ? <ValueKindBadge kind={valueKind} /> : null}
      </div>
    </div>
  );
}
