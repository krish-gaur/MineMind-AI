"use client";

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartTable } from "@/components/charts/ChartTable";
import { formatMonth, formatNumber, formatPercent } from "@/lib/format";
import type { MonthlyPoint } from "@/lib/types";

export function MonthlyTrendChart({ points }: { points: MonthlyPoint[] }) {
  const data = points.map((point) => ({
    month: point.month,
    label: formatMonth(point.month),
    planned: point.planned_t ?? 0,
    actual: point.actual_t ?? 0,
    attainment: point.attainment_pct,
  }));
  const summary = `Monthly planned and actual tonnes with attainment, ${points.length} month(s).`;

  return (
    <figure aria-label={summary} className="w-full">
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#eceff1" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#5d656a" }} tickLine={false} axisLine={false} />
            <YAxis
              yAxisId="tonnes"
              tick={{ fontSize: 11, fill: "#5d656a" }}
              tickFormatter={(value: number) => formatNumber(value)}
              width={72}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              yAxisId="pct"
              orientation="right"
              domain={[0, (max: number) => Math.max(110, Math.ceil(max))]}
              tick={{ fontSize: 11, fill: "#5d656a" }}
              tickFormatter={(value: number) => `${value}%`}
              width={48}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              formatter={(value, name) => {
                if (name === "Attainment") return [formatPercent(Number(value)), name];
                return [`${formatNumber(Number(value))} t`, name];
              }}
              contentStyle={{ fontSize: 12, borderRadius: 6, borderColor: "#dfdacd" }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar yAxisId="tonnes" dataKey="planned" name="Planned" fill="#b9c0c5" radius={[3, 3, 0, 0]} />
            <Bar yAxisId="tonnes" dataKey="actual" name="Actual" fill="#1f4d3a" radius={[3, 3, 0, 0]} />
            <Line
              yAxisId="pct"
              type="monotone"
              dataKey="attainment"
              name="Attainment"
              stroke="#c98a1b"
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <ChartTable
        caption={summary}
        columns={[
          { key: "month", header: "Month" },
          { key: "planned", header: "Planned (t)", align: "right" },
          { key: "actual", header: "Actual (t)", align: "right" },
          { key: "attainment", header: "Attainment", align: "right" },
        ]}
        rows={data.map((row) => ({
          month: row.label,
          planned: formatNumber(row.planned),
          actual: formatNumber(row.actual),
          attainment: row.attainment === null ? "n/a" : formatPercent(row.attainment),
        }))}
      />
    </figure>
  );
}
