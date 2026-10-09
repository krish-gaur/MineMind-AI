"use client";

import { useState } from "react";
import { DatasetList } from "@/components/data/DatasetList";
import { SourcesTable } from "@/components/data/SourcesTable";
import { SyntheticBanner } from "@/components/data/SyntheticBanner";
import { UploadForm } from "@/components/data/UploadForm";
import { ValidationReportView } from "@/components/data/ValidationReportView";
import { PageHeader } from "@/components/layout/PageHeader";
import { SourceBadge } from "@/components/ui/Badges";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/States";
import { useDatasets } from "@/lib/dataset-context";
import { formatDateTime, formatNumber } from "@/lib/format";
import type {
  DatasetDetail,
  DatasetPreview,
  ProductionSchema,
  SourcesResponse,
} from "@/lib/types";
import { useApiResource } from "@/lib/useApiResource";

export default function DataPage() {
  const { datasets, datasetsError, active, reloadDatasets, selectDataset } = useDatasets();
  const schema = useApiResource<ProductionSchema>("/api/datasets/schema/production");
  const sources = useApiResource<SourcesResponse>("/api/meta/sources");
  const [justStored, setJustStored] = useState<string | null>(null);

  return (
    <>
      <PageHeader
        title="Data and sources"
        description="Register production records, check how they were validated, and see where every figure comes from. Uploads are validated before anything is stored."
      />

      <div className="space-y-6">
        <Card labelledBy="datasets-title">
          <CardHeader
            id="datasets-title"
            title="Registered datasets"
            description="The active dataset feeds the overview, forecasts, risk and reports."
          />
          {datasetsError ? (
            <ErrorState error={datasetsError} onRetry={reloadDatasets} title="Datasets could not be loaded" />
          ) : datasets === null ? (
            <LoadingBlock label="Loading datasets" />
          ) : datasets.length === 0 ? (
            <div className="p-5">
              <EmptyState title="No datasets are registered yet." />
            </div>
          ) : (
            <DatasetList datasets={datasets} />
          )}
        </Card>

        <Card labelledBy="upload-title">
          <CardHeader
            id="upload-title"
            title="Upload production records"
            description="CSV in the production.v1 format. Errors block storage and are listed by file line."
          />
          <div className="p-5">
            {schema.error ? (
              <ErrorState error={schema.error} onRetry={schema.reload} title="Schema could not be loaded" />
            ) : (
              <UploadForm
                schema={schema.data}
                onStored={(stored: DatasetDetail) => {
                  setJustStored(stored.id);
                  reloadDatasets();
                  selectDataset(stored.id);
                }}
              />
            )}
            {justStored ? <span className="sr-only">Stored dataset {justStored}</span> : null}
          </div>
        </Card>

        <Card labelledBy="selected-title">
          <CardHeader
            id="selected-title"
            title="Active dataset"
            description={active ? active.name : "Select or upload a dataset to see its validation and preview."}
          />
          <div className="space-y-6 p-5">
            {active === null ? (
              <EmptyState title="No active dataset." />
            ) : (
              <ActiveDatasetDetails datasetId={active.id} isSynthetic={active.is_synthetic} />
            )}
          </div>
        </Card>

        <Card labelledBy="contract-title">
          <CardHeader
            id="contract-title"
            title="Production CSV contract"
            description="Required and optional columns. Units are part of the header meaning, not the file."
          />
          <div className="p-5">
            {schema.loading ? <LoadingBlock rows={4} /> : null}
            {schema.error && !schema.loading ? (
              <ErrorState error={schema.error} onRetry={schema.reload} />
            ) : null}
            {schema.data ? (
              <div className="space-y-5">
                <div className="overflow-x-auto rounded border border-line">
                  <table className="w-full min-w-[720px] text-left text-sm">
                    <caption className="sr-only">Columns accepted in production CSV uploads</caption>
                    <thead className="bg-slate-100 text-xs uppercase tracking-wide text-ink-700">
                      <tr>
                        <th scope="col" className="px-3 py-2 font-semibold">Column</th>
                        <th scope="col" className="px-3 py-2 font-semibold">Required</th>
                        <th scope="col" className="px-3 py-2 font-semibold">Unit</th>
                        <th scope="col" className="px-3 py-2 font-semibold">Meaning</th>
                      </tr>
                    </thead>
                    <tbody>
                      {schema.data.columns.map((column) => (
                        <tr key={column.name} className="border-t border-line align-top">
                          <td className="px-3 py-2 font-mono text-xs font-medium">{column.name}</td>
                          <td className="px-3 py-2">{column.required ? "Yes" : "Optional"}</td>
                          <td className="px-3 py-2 text-ink-700">{column.unit}</td>
                          <td className="px-3 py-2 text-ink-700">{column.description}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div>
                  <p className="text-sm font-medium text-ink-900">Example</p>
                  <pre className="mt-2 overflow-x-auto rounded border border-line bg-slate-100 p-3 font-mono text-xs text-ink-900">
                    {schema.data.example_csv}
                  </pre>
                  <TemplateDownload csv={schema.data.example_csv} />
                </div>
              </div>
            ) : null}
          </div>
        </Card>

        <Card labelledBy="sources-title">
          <CardHeader
            id="sources-title"
            title="Data sources, licences and limitations"
            description="Every public source used by MineMind AI, with its terms and what it cannot tell you."
          />
          <div className="space-y-4 p-5">
            <SyntheticBanner text="The synthetic production records are generated by MineMind AI for demonstration. They are not MOIL data." />
            {sources.loading ? <LoadingBlock rows={3} /> : null}
            {sources.error ? <ErrorState error={sources.error} onRetry={sources.reload} /> : null}
            {sources.data ? <SourcesTable sources={sources.data.sources} /> : null}
          </div>
        </Card>
      </div>
    </>
  );
}

function ActiveDatasetDetails({ datasetId, isSynthetic }: { datasetId: string; isSynthetic: boolean }) {
  const detail = useApiResource<DatasetDetail>(`/api/datasets/${encodeURIComponent(datasetId)}`);
  const preview = useApiResource<DatasetPreview>(`/api/datasets/${encodeURIComponent(datasetId)}/preview`, {
    rows: 20,
  });

  if (detail.loading) return <LoadingBlock rows={4} />;
  if (detail.error) return <ErrorState error={detail.error} onRetry={detail.reload} />;
  if (!detail.data) return null;
  const info = detail.data;

  return (
    <>
      {isSynthetic ? <SyntheticBanner /> : null}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <SourceBadge sourceType={info.source_type} />
            <span className="text-xs text-ink-500">{info.kind}</span>
          </div>
          <p className="text-ink-900">{info.provenance.description}</p>
          <dl className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <dt className="text-ink-500">Stored</dt>
              <dd className="font-medium text-ink-900">{formatDateTime(info.created_at)}</dd>
            </div>
            <div>
              <dt className="text-ink-500">Size</dt>
              <dd className="font-medium text-ink-900">{formatNumber(info.size_bytes)} bytes</dd>
            </div>
            <div className="col-span-2">
              <dt className="text-ink-500">SHA-256</dt>
              <dd className="break-all font-mono text-[11px] text-ink-900">{info.sha256}</dd>
            </div>
            {info.original_filename ? (
              <div className="col-span-2">
                <dt className="text-ink-500">Original file name (sanitised)</dt>
                <dd className="font-mono text-ink-900">{info.original_filename}</dd>
              </div>
            ) : null}
          </dl>
          {info.provenance.limitations.length > 0 ? (
            <details className="rounded border border-line bg-slate-100/60 p-3">
              <summary className="cursor-pointer font-medium text-ink-900">Limitations</summary>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-ink-700">
                {info.provenance.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>

        <div className="lg:col-span-2">
          <h3 className="mb-3 text-sm font-semibold text-ink-900">Validation report</h3>
          {info.validation ? (
            <ValidationReportView report={info.validation} />
          ) : (
            <p className="text-sm text-ink-500">No validation report is stored for this dataset.</p>
          )}
        </div>
      </div>

      <div>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-ink-900">
            Preview (first {preview.data?.returned_rows ?? 20} of {formatNumber(info.row_count)} rows)
          </h3>
          <a
            href={`/api/datasets/${encodeURIComponent(datasetId)}/export`}
            className="text-xs font-medium text-forest-800 underline"
          >
            Download normalised CSV
          </a>
        </div>
        {preview.loading ? <LoadingBlock rows={3} /> : null}
        {preview.error ? <ErrorState error={preview.error} onRetry={preview.reload} /> : null}
        {preview.data ? <PreviewTable columns={preview.data.columns} rows={preview.data.rows} /> : null}
      </div>
    </>
  );
}

function PreviewTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: DatasetPreview["rows"];
}) {
  return (
    <div className="overflow-x-auto rounded border border-line">
      <table className="w-full min-w-[900px] text-left text-xs">
        <caption className="sr-only">First rows of the active dataset. Blank values are missing in the source.</caption>
        <thead className="bg-slate-100 text-ink-700">
          <tr>
            {columns.map((column) => (
              <th key={column} scope="col" className="whitespace-nowrap px-3 py-2 font-semibold">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="border-t border-line">
              {columns.map((column) => {
                const value = row[column];
                const missing = value === null || value === "";
                return (
                  <td key={column} className={`tabular whitespace-nowrap px-3 py-1.5 ${missing ? "text-ink-500" : ""}`}>
                    {missing ? <span aria-label="missing value">blank</span> : String(value)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TemplateDownload({ csv }: { csv: string }) {
  function download() {
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "minemind-production-template.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }
  return (
    <button
      type="button"
      onClick={download}
      className="mt-3 rounded-md border border-line-strong bg-white px-3 py-1.5 text-sm font-medium text-ink-900 hover:bg-slate-100"
    >
      Download template CSV
    </button>
  );
}
