import { StatusPill, type Tone } from "@/components/ui/Badges";
import { formatNumber } from "@/lib/format";
import type { ValidationReport } from "@/lib/types";

const STATUS: Record<ValidationReport["status"], { label: string; tone: Tone }> = {
  valid: { label: "Valid", tone: "good" },
  valid_with_warnings: { label: "Valid with warnings", tone: "warn" },
  invalid: { label: "Invalid. Not stored", tone: "bad" },
};

export function ValidationReportView({ report }: { report: ValidationReport }) {
  const status = STATUS[report.status];
  const errors = report.issues.filter((issue) => issue.severity === "error");
  const warnings = report.issues.filter((issue) => issue.severity === "warning");
  return (
    <div className="space-y-5 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <StatusPill tone={status.tone}>{status.label}</StatusPill>
        <span className="text-ink-500">
          {formatNumber(report.row_count)} rows · schema {report.schema_version}
          {report.status !== "invalid" ? (
            <>
              {" "}
              · {formatNumber(report.rows_with_actual)} with actuals · {formatNumber(report.rows_pending_actual)} pending
            </>
          ) : null}
        </span>
      </div>

      {errors.length > 0 ? (
        <IssueList title="Errors (must be fixed)" issues={errors} tone="bad" />
      ) : null}
      {warnings.length > 0 ? (
        <IssueList title="Warnings (accepted, review recommended)" issues={warnings} tone="warn" />
      ) : null}
      {report.issues.length === 0 ? (
        <p className="text-ink-700">No problems were found in the schema, ranges, keys or dates.</p>
      ) : null}

      {report.columns.length > 0 ? (
        <div className="overflow-x-auto rounded border border-line">
          <table className="w-full min-w-[640px] text-left text-xs">
            <caption className="sr-only">Column profile from validation</caption>
            <thead className="bg-slate-100 text-ink-700">
              <tr>
                <th scope="col" className="px-3 py-2 font-semibold">Column</th>
                <th scope="col" className="px-3 py-2 font-semibold">Required</th>
                <th scope="col" className="px-3 py-2 font-semibold">Present</th>
                <th scope="col" className="px-3 py-2 text-right font-semibold">Missing</th>
                <th scope="col" className="px-3 py-2 text-right font-semibold">Min</th>
                <th scope="col" className="px-3 py-2 text-right font-semibold">Max</th>
                <th scope="col" className="px-3 py-2 text-right font-semibold">Mean</th>
                <th scope="col" className="px-3 py-2 text-right font-semibold">Outliers</th>
              </tr>
            </thead>
            <tbody>
              {report.columns.map((column) => (
                <tr key={column.name} className="border-t border-line">
                  <td className="px-3 py-1.5 font-mono">{column.name}</td>
                  <td className="px-3 py-1.5">{column.required ? "Yes" : "Optional"}</td>
                  <td className="px-3 py-1.5">{column.present ? "Yes" : "No"}</td>
                  <td className="tabular px-3 py-1.5 text-right">
                    {column.present && column.missing_pct !== null
                      ? `${formatNumber(column.missing_count)} (${column.missing_pct}%)`
                      : "n/a"}
                  </td>
                  <td className="tabular px-3 py-1.5 text-right">{column.min ?? "n/a"}</td>
                  <td className="tabular px-3 py-1.5 text-right">{column.max ?? "n/a"}</td>
                  <td className="tabular px-3 py-1.5 text-right">{column.mean ?? "n/a"}</td>
                  <td className="tabular px-3 py-1.5 text-right">
                    {column.outlier_count > 0 ? formatNumber(column.outlier_count) : "0"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {report.unknown_columns.length > 0 ? (
        <p className="text-xs text-ink-500">
          Ignored columns: <span className="font-mono">{report.unknown_columns.join(", ")}</span>
        </p>
      ) : null}
    </div>
  );
}

function IssueList({
  title,
  issues,
  tone,
}: {
  title: string;
  issues: ValidationReport["issues"];
  tone: "bad" | "warn";
}) {
  const border = tone === "bad" ? "border-brick-500" : "border-amber-500";
  return (
    <div>
      <h3 className="font-semibold text-ink-900">{title}</h3>
      <ul className="mt-2 space-y-2">
        {issues.map((issue, index) => (
          <li key={`${issue.code}-${index}`} className={`rounded border-l-4 ${border} bg-white px-3 py-2`}>
            <p className="text-ink-900">
              {issue.message}
              {issue.affected_rows > 0 ? (
                <span className="ml-2 text-xs text-ink-500">({formatNumber(issue.affected_rows)} affected)</span>
              ) : null}
            </p>
            {issue.examples.length > 0 ? (
              <ul className="mt-1 list-disc pl-5 font-mono text-xs text-ink-700">
                {issue.examples.map((example) => (
                  <li key={example}>{example}</li>
                ))}
              </ul>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
