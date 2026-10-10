import type { ReactNode } from "react";
import { ApiError } from "@/lib/api";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded bg-slate-100 ${className}`} />;
}

export function LoadingBlock({ label = "Loading", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3 p-5">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-6 w-full" />
      ))}
    </div>
  );
}

/** Explains a failure in plain language. Never shows raw response bodies. */
export function describeError(error: unknown): { title: string; message: string; requestId: string | null } {
  if (error instanceof ApiError) {
    if (error.code === "network_error") {
      return {
        title: "Backend unreachable",
        message: error.message,
        requestId: null,
      };
    }
    if (error.status === 422 || error.code === "validation_failed") {
      return { title: "Check the request", message: error.message, requestId: error.requestId };
    }
    if (error.status === 404) {
      return { title: "Not found", message: error.message, requestId: error.requestId };
    }
    return { title: "Something went wrong", message: error.message, requestId: error.requestId };
  }
  return {
    title: "Something went wrong",
    message: "The page could not load this information. Try again.",
    requestId: null,
  };
}

export function ErrorState({
  error,
  onRetry,
  title,
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}) {
  const described = describeError(error);
  return (
    <div role="alert" className="m-5 rounded-md border border-brick-500/40 bg-brick-100 p-4 text-brick-800">
      <p className="font-semibold">{title ?? described.title}</p>
      <p className="mt-1 text-sm">{described.message}</p>
      {described.requestId ? (
        <p className="mt-2 font-mono text-xs text-brick-700">Reference: {described.requestId}</p>
      ) : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded border border-brick-700 bg-white px-3 py-1.5 text-sm font-medium text-brick-800 hover:bg-brick-100"
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-start gap-2 p-6 text-sm text-ink-700">
      <p className="font-semibold text-ink-900">{title}</p>
      {children ? <div className="text-ink-500">{children}</div> : null}
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}
