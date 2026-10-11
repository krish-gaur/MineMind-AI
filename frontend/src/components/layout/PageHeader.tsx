import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
  actions,
  status,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  status?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{title}</h1>
        {description ? <p className="mt-1.5 max-w-3xl text-sm text-ink-500">{description}</p> : null}
      </div>
      {actions || status ? (
        <div className="flex flex-wrap items-center gap-3">
          {status}
          {actions}
        </div>
      ) : null}
    </header>
  );
}
