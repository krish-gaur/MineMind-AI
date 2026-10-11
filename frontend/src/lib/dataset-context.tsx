"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, apiGet } from "./api";
import type { DatasetList, DatasetSummary } from "./types";

const STORAGE_KEY = "minemind.datasetId";
const DEMO_ID = "demo-synthetic-production-v1";

type DatasetContextValue = {
  /** Every registered dataset (production, drillholes and exploration zones). */
  datasets: DatasetSummary[] | null;
  /** Production datasets only: the ones analysis pages can use. */
  productionDatasets: DatasetSummary[] | null;
  datasetsError: Error | null;
  /** Currently selected production dataset (null while loading or when none exists). */
  active: DatasetSummary | null;
  selectDataset: (id: string) => void;
  reloadDatasets: () => void;
};

const DatasetContext = createContext<DatasetContextValue | null>(null);

export function DatasetProvider({ children }: { children: React.ReactNode }) {
  const [datasets, setDatasets] = useState<DatasetSummary[] | null>(null);
  const [datasetsError, setDatasetsError] = useState<Error | null>(null);
  // Read the saved selection once. The first render does not depend on it, so the
  // server and client markup still match during hydration.
  const [selectedId, setSelectedId] = useState<string | null>(() =>
    typeof window === "undefined" ? null : window.localStorage.getItem(STORAGE_KEY),
  );
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    apiGet<DatasetList>("/api/datasets", undefined, controller.signal)
      .then((body) => {
        setDatasets(body.datasets);
        setDatasetsError(null);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setDatasetsError(error instanceof Error ? error : new ApiError("Unknown error", { status: 0, code: "unknown" }));
      });
    return () => controller.abort();
  }, [attempt]);

  const selectDataset = useCallback((id: string) => {
    setSelectedId(id);
    window.localStorage.setItem(STORAGE_KEY, id);
  }, []);

  const reloadDatasets = useCallback(() => setAttempt((n) => n + 1), []);

  const value = useMemo<DatasetContextValue>(() => {
    const production = datasets?.filter((d) => d.kind === "production") ?? null;
    const list = production ?? [];
    const active =
      list.find((d) => d.id === selectedId) ?? list.find((d) => d.id === DEMO_ID) ?? list[0] ?? null;
    return {
      datasets,
      productionDatasets: production,
      datasetsError,
      active,
      selectDataset,
      reloadDatasets,
    };
  }, [datasets, datasetsError, selectedId, selectDataset, reloadDatasets]);

  return <DatasetContext.Provider value={value}>{children}</DatasetContext.Provider>;
}

export function useDatasets(): DatasetContextValue {
  const context = useContext(DatasetContext);
  if (!context) {
    throw new Error("useDatasets must be used inside DatasetProvider.");
  }
  return context;
}
