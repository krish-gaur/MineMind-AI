"use client";

import { addDays } from "@/lib/format";
import type { DatasetSummary } from "@/lib/types";

export type RangePreset = "30d" | "90d" | "365d" | "all" | "custom";

export const RANGE_OPTIONS: { value: RangePreset; label: string }[] = [
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "365d", label: "Last 12 months" },
  { value: "all", label: "All dates" },
  { value: "custom", label: "Custom" },
];

const PRESET_DAYS: Partial<Record<RangePreset, number>> = { "30d": 30, "90d": 90, "365d": 365 };

export type ResolvedRange = { start?: string; end?: string };

/** Turn a preset (anchored on the dataset's latest actual date) into concrete bounds. */
export function resolveRange(
  preset: RangePreset,
  dataset: DatasetSummary | null,
  custom: { start: string; end: string },
): ResolvedRange {
  if (preset === "custom") {
    return { start: custom.start || undefined, end: custom.end || undefined };
  }
  const days = PRESET_DAYS[preset];
  if (!days || !dataset?.date_max) return {};
  return { start: addDays(dataset.date_max, -(days - 1)), end: dataset.date_max };
}

type Props = {
  dataset: DatasetSummary;
  preset: RangePreset;
  onPreset: (value: RangePreset) => void;
  custom: { start: string; end: string };
  onCustom: (value: { start: string; end: string }) => void;
  mineId: string;
  onMine: (value: string) => void;
  zoneId: string;
  onZone: (value: string) => void;
};

const selectClass =
  "rounded-md border border-line-strong bg-white px-2.5 py-2 text-sm text-ink-900 disabled:opacity-60";

export function OverviewFilters(props: Props) {
  const { dataset, preset, onPreset, custom, onCustom, mineId, onMine, zoneId, onZone } = props;
  return (
    <form
      aria-label="Overview filters"
      className="grid gap-3 rounded-lg border border-line bg-surface p-4 lg:grid-cols-[auto_auto_auto_auto]"
      onSubmit={(event) => event.preventDefault()}
    >
      <fieldset className="flex flex-wrap items-center gap-1.5">
        <legend className="sr-only">Date range</legend>
        {RANGE_OPTIONS.map((option) => {
          const selected = preset === option.value;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={selected}
              onClick={() => onPreset(option.value)}
              className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                selected
                  ? "border-forest-800 bg-forest-800 text-white"
                  : "border-line-strong bg-white text-ink-700 hover:bg-slate-100"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </fieldset>

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1.5 text-xs text-ink-500">
          From
          <input
            type="date"
            className={selectClass}
            value={custom.start}
            min={dataset.date_min ?? undefined}
            max={dataset.date_max ?? undefined}
            onChange={(event) => {
              onCustom({ ...custom, start: event.target.value });
              onPreset("custom");
            }}
          />
        </label>
        <label className="flex items-center gap-1.5 text-xs text-ink-500">
          To
          <input
            type="date"
            className={selectClass}
            value={custom.end}
            min={dataset.date_min ?? undefined}
            max={dataset.date_max ?? undefined}
            onChange={(event) => {
              onCustom({ ...custom, end: event.target.value });
              onPreset("custom");
            }}
          />
        </label>
      </div>

      <label className="flex items-center gap-1.5 text-xs text-ink-500">
        Mine
        <select
          className={selectClass}
          value={mineId}
          onChange={(event) => {
            onMine(event.target.value);
            onZone("");
          }}
        >
          <option value="">All mines</option>
          {dataset.mines.map((mine) => (
            <option key={mine} value={mine}>
              {mine}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-1.5 text-xs text-ink-500">
        Zone
        <select className={selectClass} value={zoneId} onChange={(event) => onZone(event.target.value)}>
          <option value="">All zones</option>
          {dataset.zones.map((zone) => (
            <option key={zone} value={zone}>
              {zone}
            </option>
          ))}
        </select>
      </label>
    </form>
  );
}
