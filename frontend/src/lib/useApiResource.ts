"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, type QueryParams } from "./api";

export type ResourceState<T> = {
  /** Data for the current query only. Null while a different query is loading. */
  data: T | null;
  error: Error | null;
  /** First load for the current query (no data yet). */
  loading: boolean;
  /** A reload of the current query is in flight; existing data stays visible. */
  refreshing: boolean;
  reload: () => void;
};

type Settled<T> = {
  queryKey: string;
  attempt: number;
  data: T | null;
  error: Error | null;
};

/**
 * Fetch a GET resource whenever the path or params change.
 *
 * Results are tagged with the query they answer, so data from a previous
 * dataset or filter is never shown under the current selection. Passing a null
 * path skips the request.
 */
export function useApiResource<T>(path: string | null, params?: QueryParams): ResourceState<T> {
  const paramKey = JSON.stringify(params ?? {});
  const queryKey = path === null ? null : `${path}?${paramKey}`;
  const [attempt, setAttempt] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);

  useEffect(() => {
    if (path === null) return;
    const controller = new AbortController();
    const key = `${path}?${paramKey}`;
    const attemptAtStart = attempt;
    apiGet<T>(path, JSON.parse(paramKey) as QueryParams, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setSettled({ queryKey: key, attempt: attemptAtStart, data, error: null });
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        const normalised = error instanceof Error ? error : new Error("Unknown error");
        setSettled({ queryKey: key, attempt: attemptAtStart, data: null, error: normalised });
      });
    return () => controller.abort();
  }, [path, paramKey, attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  const current = settled !== null && queryKey !== null && settled.queryKey === queryKey ? settled : null;
  if (queryKey === null) {
    return { data: null, error: null, loading: false, refreshing: false, reload };
  }
  return {
    data: current?.data ?? null,
    error: current?.error ?? null,
    loading: current === null,
    refreshing: current !== null && current.attempt !== attempt,
    reload,
  };
}
