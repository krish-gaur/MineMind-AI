"use client";

import type { ReactNode } from "react";
import type { DatasetSummary } from "@/lib/types";

const selectClass =
  "rounded-md border border-line-strong bg-white px-2.5 py-2 text-sm text-ink-900 disabled:opacity-60";

type Props = {
  dataset: DatasetSummary;
  mineId: string;
  zoneId: string;
  onMine: (value: string) => void;
  onZone: (value: string) => void;
  horizon?: number;
  onHorizon?: (value: number) => void;
  children?: ReactNode;
};

/** Mine, zone and (optionally) horizon selectors. Zones are limited to the chosen mine. */
export function ScopeFilters({ dataset, mineId, zoneId, onMine, onZone, horizon, onHorizon, children }: Props) {
  const zones = mineId ? (dataset.mine_zones[mineId] ?? []) : dataset.zones;
  return (
    <form
      aria-label="Scope and horizon"
      className="flex flex-wrap items-end gap-4 rounded-lg border border-line bg-surface p-4"
      onSubmit={(event) => event.preventDefault()}
    >
      <label className="flex flex-col gap-1 text-xs text-ink-500">
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
      <label className="flex flex-col gap-1 text-xs text-ink-500">
        Zone
        <select className={selectClass} value={zoneId} onChange={(event) => onZone(event.target.value)}>
          <option value="">All zones{mineId ? ` in ${mineId}` : ""}</option>
          {zones.map((zone) => (
            <option key={zone} value={zone}>
              {zone}
            </option>
          ))}
        </select>
      </label>
      {onHorizon && horizon !== undefined ? (
        <label className="flex flex-col gap-1 text-xs text-ink-500">
          Forecast horizon
          <select
            className={selectClass}
            value={horizon}
            onChange={(event) => onHorizon(Number(event.target.value))}
          >
            {[30, 60, 90].map((days) => (
              <option key={days} value={days}>
                {days} days
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {children}
    </form>
  );
}
