"use client";

import { useId, useRef, useState } from "react";
import { ValidationReportView } from "@/components/data/ValidationReportView";
import { ApiError, apiUpload } from "@/lib/api";
import type { DatasetDetail, ProductionSchema, ValidationReport } from "@/lib/types";

type Props = {
  schema: ProductionSchema | null;
  onStored: (dataset: DatasetDetail) => void;
};

export function UploadForm({ schema, onStored }: Props) {
  const inputId = useId();
  const nameId = useId();
  const descId = useId();
  const fileRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const maxMb = schema?.max_upload_mb ?? 5;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setFailure(null);
    setReport(null);
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setFailure("Choose a CSV file first.");
      return;
    }
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setFailure("Only .csv files are accepted for production records.");
      return;
    }
    if (file.size > maxMb * 1024 * 1024) {
      setFailure(`This file is ${(file.size / (1024 * 1024)).toFixed(1)} MB. The limit is ${maxMb} MB.`);
      return;
    }
    const form = new FormData();
    form.append("file", file);
    if (name.trim()) form.append("name", name.trim());
    if (description.trim()) form.append("description", description.trim());
    form.append("kind", "production");

    setBusy(true);
    try {
      const stored = await apiUpload<DatasetDetail>("/api/datasets", form);
      setMessage(`Stored "${stored.name}" (${stored.row_count.toLocaleString("en-US")} rows). It is now the active dataset.`);
      setName("");
      setDescription("");
      if (fileRef.current) fileRef.current.value = "";
      onStored(stored);
    } catch (error) {
      if (error instanceof ApiError) {
        const details = error.details as ValidationReport | null;
        if (details && typeof details === "object" && "issues" in details) {
          setReport(details);
          setFailure("The file was not stored. Fix the problems listed below and upload again.");
        } else {
          setFailure(error.message);
        }
      } else {
        setFailure("The upload could not be completed. Try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" aria-describedby={descId}>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <label htmlFor={inputId} className="block text-sm font-medium text-ink-900">
            Production CSV
          </label>
          <input
            id={inputId}
            ref={fileRef}
            type="file"
            accept=".csv,text/csv"
            required
            className="mt-1.5 block w-full rounded-md border border-line-strong bg-white p-2 text-sm file:mr-3 file:rounded file:border-0 file:bg-forest-800 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white"
          />
          <p id={descId} className="mt-1.5 text-xs text-ink-500">
            UTF-8 CSV with a header row. Maximum {maxMb} MB
            {schema ? ` and ${schema.max_upload_rows.toLocaleString("en-US")} rows` : ""}. Blank actuals are kept as
            pending; nothing is imputed.
          </p>
        </div>
        <div className="space-y-3">
          <div>
            <label htmlFor={nameId} className="block text-sm font-medium text-ink-900">
              Display name <span className="font-normal text-ink-500">(optional)</span>
            </label>
            <input
              id={nameId}
              value={name}
              maxLength={120}
              onChange={(event) => setName(event.target.value)}
              className="mt-1.5 w-full rounded-md border border-line-strong bg-white px-3 py-2 text-sm"
              placeholder="e.g. Pilot extract, Q2 records"
            />
          </div>
          <div>
            <label htmlFor={`${nameId}-desc`} className="block text-sm font-medium text-ink-900">
              Description <span className="font-normal text-ink-500">(optional)</span>
            </label>
            <input
              id={`${nameId}-desc`}
              value={description}
              maxLength={400}
              onChange={(event) => setDescription(event.target.value)}
              className="mt-1.5 w-full rounded-md border border-line-strong bg-white px-3 py-2 text-sm"
            />
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-forest-800 px-4 py-2 text-sm font-medium text-white hover:bg-forest-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy ? "Validating..." : "Validate and store"}
        </button>
        <p className="text-xs text-ink-500">Uploaded data is labelled USER-PROVIDED and is not verified by MineMind AI.</p>
      </div>

      {message ? (
        <p role="status" className="rounded-md border border-forest-200 bg-forest-50 px-3 py-2 text-sm text-forest-900">
          {message}
        </p>
      ) : null}
      {failure ? (
        <p role="alert" className="rounded-md border border-brick-500/40 bg-brick-100 px-3 py-2 text-sm text-brick-800">
          {failure}
        </p>
      ) : null}
      {report ? (
        <div className="rounded-md border border-line p-4">
          <ValidationReportView report={report} />
        </div>
      ) : null}
    </form>
  );
}
