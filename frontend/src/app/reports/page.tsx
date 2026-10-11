"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { SyntheticBanner } from "@/components/data/SyntheticBanner";
import { PageHeader } from "@/components/layout/PageHeader";
import { ScopeFilters } from "@/components/scope/ScopeFilters";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState, LoadingBlock } from "@/components/ui/States";
import { ApiError, apiPostDownload } from "@/lib/api";
import { useDatasets } from "@/lib/dataset-context";
import { VALUE_KIND_HELP } from "@/lib/labels";
import type { DatasetSummary } from "@/lib/types";

const SECTIONS: { id: string; label: string; help: string }[] = [
  { id: "overview", label: "Overview KPIs and zones", help: "Measured values from the dataset." },
  { id: "forecast", label: "Forecast and backtest", help: "Model outputs with baseline comparison." },
  { id: "risk", label: "Shortfall risk", help: "Expected gap (estimate) and rule-based band." },
  { id: "recommendations", label: "Recommendations", help: "Rule outputs with evidence and rules checked." },
  { id: "exploration", label: "Exploration zone index", help: "Index from geological and drilling evidence." },
  { id: "sources", label: "Data sources and licences", help: "Licences, attributions and limitations." },
];

export default function ReportsPage() {
  const { active, productionDatasets, datasetsError, reloadDatasets } = useDatasets();
  if (datasetsError) {
    return (
      <>
        <PageHeader title="Reports" />
        <Card>
          <EmptyState title="Datasets could not be loaded.">
            <button type="button" className="underline" onClick={reloadDatasets}>Try again</button>
          </EmptyState>
        </Card>
      </>
    );
  }
  if (productionDatasets === null) return <LoadingBlock label="Loading datasets" />;
  if (active === null) {
    return (
      <>
        <PageHeader title="Reports" />
        <Card>
          <EmptyState title="A production dataset is needed to build a report.">
            <Link href="/data" className="font-medium text-forest-800 underline">Upload production records</Link>
          </EmptyState>
        </Card>
      </>
    );
  }
  return <ReportForm key={active.id} dataset={active} />;
}

function ReportForm({ dataset }: { dataset: DatasetSummary }) {
  const titleId = useId();
  const [mineId, setMineId] = useState("");
  const [zoneId, setZoneId] = useState("");
  const [horizon, setHorizon] = useState(30);
  const [title, setTitle] = useState("MineMind AI decision summary");
  const [format, setFormat] = useState<"html" | "json">("html");
  const [selected, setSelected] = useState<string[]>(SECTIONS.map((s) => s.id));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  async function generate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selected.length === 0) {
      setMessage({ tone: "error", text: "Choose at least one section." });
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const { blob, filename } = await apiPostDownload("/api/reports", {
        dataset_id: dataset.id,
        mine_id: mineId || null,
        zone_id: zoneId || null,
        horizon_days: horizon,
        sections: selected,
        format,
        title,
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setMessage({ tone: "ok", text: `Downloaded ${filename}. Open the HTML file in a browser to read it.` });
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof ApiError ? error.message : "The report could not be generated. Try again.",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Reports"
        description="Build a self-contained report for a scope. Every figure is labelled with its value type and its source, and synthetic data is flagged at the top."
      />
      {dataset.is_synthetic ? <SyntheticBanner text="This report would describe synthetic data. It is for demonstrating the workflow only." /> : null}

      <form onSubmit={generate} className="mt-5 space-y-6">
        <ScopeFilters
          dataset={dataset}
          mineId={mineId}
          zoneId={zoneId}
          onMine={setMineId}
          onZone={setZoneId}
          horizon={horizon}
          onHorizon={setHorizon}
        />

        <div className="grid gap-6 xl:grid-cols-3">
          <Card labelledBy="sections-title" className="xl:col-span-2">
            <CardHeader id="sections-title" title="Sections to include" description="Only selected sections are computed and included." />
            <fieldset className="grid gap-3 p-5 md:grid-cols-2">
              <legend className="sr-only">Report sections</legend>
              {SECTIONS.map((section) => (
                <label key={section.id} className="flex items-start gap-3 rounded-md border border-line p-3 text-sm">
                  <input
                    type="checkbox"
                    className="mt-0.5 h-4 w-4 accent-forest-800"
                    checked={selected.includes(section.id)}
                    onChange={(event) =>
                      setSelected((current) =>
                        event.target.checked ? [...current, section.id] : current.filter((id) => id !== section.id),
                      )
                    }
                  />
                  <span>
                    <span className="block font-medium text-ink-900">{section.label}</span>
                    <span className="block text-xs text-ink-500">{section.help}</span>
                  </span>
                </label>
              ))}
            </fieldset>
          </Card>

          <Card labelledBy="output-title">
            <CardHeader id="output-title" title="Output" />
            <div className="space-y-4 p-5 text-sm">
              <div>
                <label htmlFor={titleId} className="block font-medium text-ink-900">Report title</label>
                <input
                  id={titleId}
                  value={title}
                  maxLength={120}
                  onChange={(event) => setTitle(event.target.value)}
                  className="mt-1.5 w-full rounded-md border border-line-strong bg-white px-3 py-2"
                />
              </div>
              <fieldset>
                <legend className="font-medium text-ink-900">Format</legend>
                <div className="mt-2 flex gap-4">
                  {(["html", "json"] as const).map((option) => (
                    <label key={option} className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="format"
                        value={option}
                        checked={format === option}
                        onChange={() => setFormat(option)}
                        className="accent-forest-800"
                      />
                      {option === "html" ? "HTML (readable)" : "JSON (machine-readable)"}
                    </label>
                  ))}
                </div>
              </fieldset>
              <button
                type="submit"
                disabled={busy}
                className="w-full rounded-md bg-forest-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-forest-700 disabled:opacity-60"
              >
                {busy ? "Building report..." : "Generate and download"}
              </button>
              {message ? (
                <p role={message.tone === "error" ? "alert" : "status"} className={message.tone === "error" ? "text-brick-700" : "text-forest-800"}>
                  {message.text}
                </p>
              ) : null}
            </div>
          </Card>
        </div>

        <Card labelledBy="legend-title">
          <CardHeader id="legend-title" title="Value types used in reports" description="Each figure is tagged with one of these." />
          <dl className="grid gap-x-8 gap-y-3 p-5 text-sm md:grid-cols-2">
            {Object.entries(VALUE_KIND_HELP).map(([kind, help]) => (
              <div key={kind}>
                <dt className="font-medium capitalize text-ink-900">{kind.replaceAll("_", " ")}</dt>
                <dd className="text-xs text-ink-500">{help}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </form>
      {selected.length === 0 ? <p className="mt-4 text-sm text-ink-500">No sections selected.</p> : null}
    </>
  );
}
