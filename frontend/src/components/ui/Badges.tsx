import type { SourceType, ValueKind } from "@/lib/types";

const SOURCE_STYLES: Record<SourceType, { label: string; className: string }> = {
  synthetic: {
    label: "SYNTHETIC",
    className: "border-amber-500 bg-amber-100 text-amber-900",
  },
  user_provided: {
    label: "USER-PROVIDED",
    className: "border-slate-300 bg-slate-100 text-ink-700",
  },
  public: {
    label: "PUBLIC",
    className: "border-forest-200 bg-forest-50 text-forest-800",
  },
};

export function SourceBadge({ sourceType }: { sourceType: SourceType }) {
  const style = SOURCE_STYLES[sourceType];
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] font-semibold tracking-wide ${style.className}`}
    >
      {style.label}
    </span>
  );
}

const VALUE_KIND_LABELS: Record<ValueKind, string> = {
  measured: "Measured",
  forecast: "Forecast",
  probability: "Probability",
  estimate: "Estimate",
  scenario: "Scenario",
  rule_based: "Rule-based",
  index: "Index",
};

const VALUE_KIND_STYLES: Record<ValueKind, string> = {
  measured: "border-forest-200 bg-forest-50 text-forest-800",
  forecast: "border-sky-300 bg-sky-50 text-sky-900",
  probability: "border-sky-300 bg-sky-50 text-sky-900",
  estimate: "border-slate-300 bg-slate-100 text-ink-700",
  scenario: "border-amber-500 bg-amber-50 text-amber-900",
  rule_based: "border-slate-300 bg-white text-ink-700",
  index: "border-slate-300 bg-white text-ink-700",
};

export function ValueKindBadge({ kind }: { kind: ValueKind }) {
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] font-medium ${VALUE_KIND_STYLES[kind]}`}
      title={`Value type: ${VALUE_KIND_LABELS[kind]}`}
    >
      {VALUE_KIND_LABELS[kind]}
    </span>
  );
}

export type Tone = "neutral" | "good" | "warn" | "bad" | "info";

const TONE_STYLES: Record<Tone, string> = {
  neutral: "border-line bg-white text-ink-700",
  good: "border-forest-200 bg-forest-50 text-forest-800",
  warn: "border-amber-500 bg-amber-100 text-amber-900",
  bad: "border-brick-500 bg-brick-100 text-brick-800",
  info: "border-sky-300 bg-sky-50 text-sky-900",
};

export function StatusPill({ tone = "neutral", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONE_STYLES[tone]}`}
    >
      {children}
    </span>
  );
}
