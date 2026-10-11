import type { ReactNode } from "react";

export type ChartTableColumn = { key: string; header: string; align?: "left" | "right" };

/** Accessible alternative to a chart: the same numbers as a table, collapsed by default. */
export function ChartTable({
  caption,
  columns,
  rows,
}: {
  caption: string;
  columns: ChartTableColumn[];
  rows: Record<string, ReactNode>[];
}) {
  return (
    <details className="group mt-3 text-sm">
      <summary className="cursor-pointer select-none font-medium text-forest-800 hover:underline">
        View as table
      </summary>
      <div className="mt-2 max-h-72 overflow-auto rounded border border-line">
        <table className="w-full min-w-max text-left text-xs">
          <caption className="sr-only">{caption}</caption>
          <thead className="sticky top-0 bg-slate-100 text-ink-700">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  className={`px-3 py-2 font-semibold ${column.align === "right" ? "text-right" : "text-left"}`}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index} className="border-t border-line">
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={`tabular px-3 py-1.5 ${column.align === "right" ? "text-right" : "text-left"}`}
                  >
                    {row[column.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
