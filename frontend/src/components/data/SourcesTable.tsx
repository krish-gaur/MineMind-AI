import { SourceBadge } from "@/components/ui/Badges";
import type { DataSourceEntry } from "@/lib/types";

export function SourcesTable({ sources }: { sources: DataSourceEntry[] }) {
  return (
    <div className="space-y-4">
      {sources.map((source) => (
        <article key={source.id} className="rounded-md border border-line p-4">
          <div className="flex flex-wrap items-center gap-2">
            <SourceBadge sourceType={source.source_type} />
            <h3 className="font-semibold text-ink-900">{source.name}</h3>
          </div>
          <dl className="mt-3 grid gap-x-6 gap-y-2 text-sm md:grid-cols-2">
            <div>
              <dt className="text-xs text-ink-500">Provider</dt>
              <dd className="text-ink-900">{source.provider}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-500">Access</dt>
              <dd className="text-ink-900">{source.access}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-500">Licence</dt>
              <dd className="text-ink-900">{source.licence}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-500">Attribution</dt>
              <dd className="text-ink-900">{source.attribution}</dd>
            </div>
            <div className="md:col-span-2">
              <dt className="text-xs text-ink-500">Used for</dt>
              <dd className="text-ink-900">{source.used_for}</dd>
            </div>
          </dl>
          {source.limitations.length > 0 ? (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-ink-700">
              {source.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
          {source.url ? (
            <p className="mt-3 text-xs">
              <a href={source.url} className="text-forest-800 underline" rel="noreferrer" target="_blank">
                {source.url}
              </a>
            </p>
          ) : null}
        </article>
      ))}
    </div>
  );
}
