import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DatasetProvider } from "@/lib/dataset-context";
import OverviewPage from "../page";

const DEMO_ID = "demo-synthetic-production-v1";

const datasetList = {
  datasets: [
    {
      id: DEMO_ID,
      kind: "production",
      name: "Synthetic demonstration production",
      description: "SYNTHETIC.",
      source_type: "synthetic",
      source_label: "SYNTHETIC DEMONSTRATION DATA",
      is_synthetic: true,
      deletable: false,
      created_at: "2026-10-09T00:00:00Z",
      row_count: 6545,
      date_min: "2023-04-01",
      date_max: "2026-09-30",
      mines: ["SYN-A", "SYN-B", "SYN-C"],
      zones: ["SYN-A-Z1", "SYN-A-Z2"],
      rows_with_actual: 6300,
      rows_pending_actual: 245,
      validation_status: "valid_with_warnings",
      sha256: "abc",
    },
  ],
};

const overview = {
  dataset: {
    id: DEMO_ID,
    name: "Synthetic demonstration production",
    source_type: "synthetic",
    source_label: "SYNTHETIC DEMONSTRATION DATA",
    is_synthetic: true,
    banner: "SYNTHETIC DEMONSTRATION DATA - not MOIL operational records.",
  },
  filters: { start: null, end: null, mine_id: null, zone_id: null },
  empty: false,
  period: { start: "2025-10-10", end: "2026-09-30", days: 356, rows: 700, rows_with_actual: 690, rows_pending_actual: 10, series: 5 },
  kpis: {
    planned_t: 550000,
    actual_t: 497000,
    gap_t: -53000,
    variance_pct: -9.64,
    attainment_pct: 90.36,
    coverage_pct: 98.57,
    days_below_plan_pct: 95.1,
    equipment_downtime_h_total: 2400,
    equipment_downtime_h_per_zone_day: 3.4,
    equipment_downtime_days_over_threshold_pct: 6.2,
    value_kind: "measured",
  },
  constraints: [
    {
      key: "equipment_downtime",
      label: "Equipment downtime",
      column: "equipment_downtime_h",
      total_hours: 2400,
      share_pct: 60,
      mean_hours_per_zone_day: 3.4,
      records: 700,
      threshold_hours: 8,
      days_over_threshold: 40,
      value_kind: "measured",
    },
  ],
  monthly: [
    { month: "2026-08", planned_t: 100000, actual_t: 90000, gap_t: -10000, attainment_pct: 90, records_with_actual: 30, equipment_downtime_h_mean: 3 },
  ],
  zones: [
    {
      mine_id: "SYN-A",
      zone_id: "SYN-A-Z2",
      records: 140,
      pending_rows: 2,
      planned_t: 100000,
      actual_t: 82000,
      gap_t: -18000,
      variance_pct: -18,
      attainment_pct: 82,
      equipment_downtime_h_total: 800,
      weather_delay_h_total: 300,
      blasting_delay_h_total: 90,
    },
  ],
  freshness: { last_actual_date: "2026-09-30", days_since_last_actual: 9, stale_threshold_days: 14, status: "fresh", as_of: "2026-10-09" },
  provenance: {
    source_type: "synthetic",
    label: "SYNTHETIC DEMONSTRATION DATA",
    provider: "MineMind AI synthetic generator",
    description: "Deterministic daily production records.",
    url: null,
    licence: null,
    attribution: null,
    timestamp: null,
    limitations: ["Not MOIL operational data."],
  },
  notes: ["SYNTHETIC DEMONSTRATION DATA - not MOIL operational records."],
};

type Handler = () => Response | Promise<Response>;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function mockApi(overviewHandler: Handler) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = new URL(String(input), "http://localhost");
    if (url.pathname === "/api/datasets") return json(datasetList);
    if (url.pathname === "/api/overview") return overviewHandler();
    return json({ error: { code: "not_found", message: "Not found" } }, 404);
  });
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Executive overview page", () => {
  it("shows API-computed KPIs with the synthetic warning", async () => {
    mockApi(() => json(overview));
    render(
      <DatasetProvider>
        <OverviewPage />
      </DatasetProvider>,
    );

    expect(await screen.findByTestId("kpi-gap")).toHaveTextContent("\u221253,000 t");
    expect(screen.getByTestId("kpi-attainment")).toHaveTextContent("90.4%");
    expect(screen.getByTestId("kpi-planned")).toHaveTextContent("550,000 t");
    expect(screen.getByText("SYNTHETIC DEMONSTRATION DATA")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /Production by mine and zone/ })).toBeInTheDocument();
  });

  it("shows a retryable error instead of numbers when the request fails", async () => {
    let calls = 0;
    mockApi(() => {
      calls += 1;
      if (calls === 1) {
        return json({ error: { code: "internal_error", message: "An unexpected error occurred.", request_id: "req-42" } }, 500);
      }
      return json(overview);
    });
    render(
      <DatasetProvider>
        <OverviewPage />
      </DatasetProvider>,
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("An unexpected error occurred.");
    expect(alert).toHaveTextContent("req-42");
    expect(screen.queryByTestId("kpi-gap")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByTestId("kpi-gap")).toBeInTheDocument());
    expect(calls).toBe(2);
  });

  it("does not show figures from a previous selection", async () => {
    mockApi(() => json(overview));
    render(
      <DatasetProvider>
        <OverviewPage />
      </DatasetProvider>,
    );
    await screen.findByTestId("kpi-gap");
    fireEvent.click(screen.getByRole("button", { name: "All dates" }));
    expect(screen.getByRole("button", { name: "All dates" })).toHaveAttribute("aria-pressed", "true");
  });
});
