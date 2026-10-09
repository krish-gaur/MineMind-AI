"use client";

import { useDatasets } from "@/lib/dataset-context";

/** Chooses the production dataset used by every analysis page. */
export function DatasetSwitcher() {
  const { datasets, datasetsError, active, selectDataset, reloadDatasets } = useDatasets();

  if (datasetsError) {
    return (
      <button
        type="button"
        onClick={reloadDatasets}
        className="rounded-md border border-brick-500 bg-brick-100 px-3 py-1.5 text-xs font-medium text-brick-800"
      >
        Datasets unavailable. Retry
      </button>
    );
  }

  if (datasets === null) {
    return <span className="text-xs text-ink-500">Loading datasets...</span>;
  }

  return (
    <label className="flex min-w-0 items-center gap-2 text-xs text-ink-500">
      <span className="hidden whitespace-nowrap sm:inline">Dataset</span>
      <select
        className="max-w-[16rem] min-w-0 truncate rounded-md border border-line-strong bg-white px-2.5 py-1.5 text-sm text-ink-900"
        value={active?.id ?? ""}
        onChange={(event) => selectDataset(event.target.value)}
        disabled={datasets.length === 0}
      >
        {datasets.length === 0 ? <option value="">No datasets yet</option> : null}
        {datasets.map((dataset) => (
          <option key={dataset.id} value={dataset.id}>
            {dataset.is_synthetic ? "[SYNTHETIC] " : ""}
            {dataset.name}
          </option>
        ))}
      </select>
    </label>
  );
}
