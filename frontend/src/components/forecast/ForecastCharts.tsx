"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartTable } from "@/components/charts/ChartTable";
import { formatNumber, formatShortDate } from "@/lib/format";
import type { ForecastDay, HistoryPoint } from "@/lib/types";

const COLORS = {
  actual: "#1f4d3a",
  plan: "#8a9196",
  model: "#c98a1b",
  baseline: "#5e7bb0",
  band: "#cfe3d7",
};

const TICK = { fontSize: 11, fill: "#5d656a" };

export function BacktestChart({ history }: { history: HistoryPoint[] }) {
  const data = history.map((point) => ({
    date: point.date,
    label: formatShortDate(point.date),
    actual: point.actual_t,
    plan: point.plan_t,
    model: point.gradient_boosting_t,
    baseline: point.seasonal_naive_7_t,
  }));
  const summary = `Out-of-sample backtest, ${history.length} days: actual, plan, gradient boosting forecast and seasonal naive baseline.`;
  return (
    <figure aria-label={summary}>
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#eceff1" vertical={false} />
            <XAxis dataKey="label" tick={TICK} tickLine={false} axisLine={false} minTickGap={32} />
            <YAxis tick={TICK} tickLine={false} axisLine={false} width={64} tickFormatter={(v: number) => formatNumber(v)} />
            <Tooltip
              formatter={(value, name) => [`${formatNumber(Number(value))} t`, String(name)]}
              contentStyle={{ fontSize: 12, borderRadius: 6, borderColor: "#dfdacd" }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line type="monotone" dataKey="actual" name="Actual" stroke={COLORS.actual} strokeWidth={2} dot={false} connectNulls={false} />
            <Line type="monotone" dataKey="plan" name="Plan" stroke={COLORS.plan} strokeDasharray="4 3" dot={false} connectNulls={false} />
            <Line type="monotone" dataKey="model" name="Gradient boosting" stroke={COLORS.model} strokeWidth={2} dot={false} connectNulls={false} />
            <Line type="monotone" dataKey="baseline" name="Seasonal naive" stroke={COLORS.baseline} dot={false} connectNulls={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <ChartTable
        caption={summary}
        columns={[
          { key: "date", header: "Date" },
          { key: "actual", header: "Actual (t)", align: "right" },
          { key: "plan", header: "Plan (t)", align: "right" },
          { key: "model", header: "Gradient boosting (t)", align: "right" },
          { key: "baseline", header: "Seasonal naive (t)", align: "right" },
        ]}
        rows={data.map((row) => ({
          date: row.label,
          actual: row.actual === null ? "n/a" : formatNumber(row.actual),
          plan: row.plan === null ? "n/a" : formatNumber(row.plan),
          model: row.model === null ? "n/a" : formatNumber(row.model),
          baseline: row.baseline === null ? "n/a" : formatNumber(row.baseline),
        }))}
      />
    </figure>
  );
}

export function ForwardChart({ days }: { days: ForecastDay[] }) {
  const data = days.map((day) => ({
    date: day.date,
    label: formatShortDate(day.date),
    plan: day.plan_t,
    forecast: day.forecast_t,
    low: day.interval_low_t,
    band: Math.max(0, day.interval_high_t - day.interval_low_t),
  }));
  const summary = `Forward forecast for ${days.length} days with an approximate 10th to 90th percentile band, against plan.`;
  return (
    <figure aria-label={summary}>
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#eceff1" vertical={false} />
            <XAxis dataKey="label" tick={TICK} tickLine={false} axisLine={false} minTickGap={24} />
            <YAxis tick={TICK} tickLine={false} axisLine={false} width={64} tickFormatter={(v: number) => formatNumber(v)} />
            <Tooltip
              formatter={(value, name) => [`${formatNumber(Number(value))} t`, String(name)]}
              contentStyle={{ fontSize: 12, borderRadius: 6, borderColor: "#dfdacd" }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Area type="monotone" dataKey="low" stackId="band" stroke="none" fill="transparent" name="Band base" legendType="none" />
            <Area type="monotone" dataKey="band" stackId="band" stroke="none" fill={COLORS.band} name="Approx. 10th-90th percentile" />
            <Line type="monotone" dataKey="plan" name="Plan" stroke={COLORS.plan} strokeDasharray="4 3" dot={false} />
            <Line type="monotone" dataKey="forecast" name="Forecast" stroke={COLORS.model} strokeWidth={2} dot={false} />
            <ReferenceLine y={0} stroke="#c9c2b2" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <ChartTable
        caption={summary}
        columns={[
          { key: "date", header: "Date" },
          { key: "plan", header: "Plan (t)", align: "right" },
          { key: "forecast", header: "Forecast (t)", align: "right" },
          { key: "low", header: "Low (t)", align: "right" },
          { key: "high", header: "High (t)", align: "right" },
        ]}
        rows={days.map((day) => ({
          date: formatShortDate(day.date),
          plan: formatNumber(day.plan_t),
          forecast: formatNumber(day.forecast_t),
          low: formatNumber(day.interval_low_t),
          high: formatNumber(day.interval_high_t),
        }))}
      />
    </figure>
  );
}
