"use client";

import { SourceBadge } from "@/components/ui/Badges";
import { apiDelete } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import { useDatasets } from "@/lib/dataset-context";
import type { DatasetSummary } from "@/lib/types";
import { useState } from "react";

export function DatasetList({ datasets }: { datasets: DatasetSummary[] }) {
  const { active, selectDataset, reloadDatasets } = useDatasets();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function remove(dataset: DatasetSummary) {
    if (!window.confirm(`Delete "${dataset.name}"? This removes the stored copy and cannot be undone.`)) return;
    setBusyId(dataset.id);
    setError(null);
    try {
      await apiDelete(`/api/datasets/${encodeURIComponent(dataset.id)}`);
      if (active?.id === dataset.id) {
        selectDataset("demo-synthetic-production-v1");
      }
      reloadDatasets();
    } catch {
      setError(`"${dataset.name}" could not be deleted. Try again.`);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="overflow-x-auto">
      {error ? (
        <p role="alert" className="mb-3 rounded-md bg-brick-100 px-3 py-2 text-sm text-brick-800">
          {error}
        </p>
      ) : null}
      <table className="w-full min-w-[820px] text-left text-sm">
        <caption className="sr-only">Registered datasets. The active dataset is marked.</caption>
        <thead className="bg-slate-100 text-xs uppercase tracking-wide text-ink-700">
          <tr>
            <th scope="col" className="px-4 py-2.5 font-semibold">Dataset</th>
            <th scope="col" className="px-4 py-2.5 font-semibold">Kind</th>
            <th scope="col" className="px-4 py-2.5 font-semibold">Source</th>
            <th scope="col" className="px-4 py-2.5 text-right font-semibold">Rows</th>
            <th scope="col" className="px-4 py-2.5 font-semibold">Dates</th>
            <th scope="col" className="px-4 py-2.5 font-semibold">Validation</th>
            <th scope="col" className="px-4 py-2.5 font-semibold">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {datasets.map((dataset) => {
            const isActive = active?.id === dataset.id;
            return (
              <tr key={dataset.id} className={`border-t border-line ${isActive ? "bg-forest-50/60" : ""}`}>
                <td className="px-4 py-3">
                  <p className="font-medium text-ink-900">
                    {dataset.name}
                    {isActive ? <span className="ml-2 text-xs font-semibold text-forest-800">ACTIVE</span> : null}
                  </p>
                  <p className="mt-0.5 font-mono text-xs text-ink-500">{dataset.id}</p>
                </td>
                <td className="px-4 py-3 text-xs text-ink-700">{KIND_LABEL[dataset.kind]}</td>
                <td className="px-4 py-3">
                  <SourceBadge sourceType={dataset.source_type} />
                </td>
                <td className="tabular px-4 py-3 text-right">{formatNumber(dataset.row_count)}</td>
                <td className="px-4 py-3 text-xs text-ink-700">
                  {dataset.date_min && dataset.date_max
                    ? `${formatDate(dataset.date_min)} to ${formatDate(dataset.date_max)}`
                    : "Not dated (no time series)"}
                  <span className="block text-ink-500">
                    {dataset.kind === "production"
                      ? `${dataset.mines.length} mine(s), ${dataset.zones.length} zone(s)`
                      : `${dataset.zones.length} zone id(s)`}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-ink-700">{validationLabel(dataset.validation_status)}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap justify-end gap-2">
                    {!isActive ? (
                      <button
                        type="button"
                        onClick={() => selectDataset(dataset.id)}
                        className="rounded border border-line-strong bg-white px-2.5 py-1 text-xs font-medium text-ink-900 hover:bg-slate-100"
                      >
                        Use
                      </button>
                    ) : null}
                    <a
                      href={`/api/datasets/${encodeURIComponent(dataset.id)}/export`}
                      className="rounded border border-line-strong bg-white px-2.5 py-1 text-xs font-medium text-ink-900 hover:bg-slate-100"
                    >
                      CSV
                    </a>
                    {dataset.deletable ? (
                      <button
                        type="button"
                        onClick={() => remove(dataset)}
                        disabled={busyId === dataset.id}
                        className="rounded border border-brick-500 bg-white px-2.5 py-1 text-xs font-medium text-brick-700 hover:bg-brick-100 disabled:opacity-60"
                      >
                        Delete
                      </button>
                    ) : null}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const KIND_LABEL: Record<DatasetSummary["kind"], string> = {
  production: "Production",
  drillholes: "Drillholes",
  exploration_zones: "Exploration zones",
};

function validationLabel(status: string | null): string {
  switch (status) {
    case "valid":
      return "Valid";
    case "valid_with_warnings":
      return "Valid, with warnings";
    case "invalid":
      return "Invalid";
    default:
      return "n/a";
  }
}
