import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import RiskPage from "../risk/page";
import RecommendationsPage from "../recommendations/page";
import MapPage from "../map/page";
import ReportsPage from "../reports/page";
import { DatasetProvider } from "@/lib/dataset-context";

vi.mock("@/components/map/MineMap", () => ({
  default: () => <div data-testid="map-stub" />,
}));

const DEMO = "demo-synthetic-production-v1";
const ZONES = "demo-synthetic-exploration-zones-v1";
const HOLES = "demo-synthetic-drillholes-v1";

const datasets = {
  datasets: [
    {
      id: DEMO, kind: "production", name: "Synthetic demonstration production", description: "", source_type: "synthetic",
      source_label: "SYNTHETIC DEMONSTRATION DATA", is_synthetic: true, deletable: false, created_at: "2026-10-09T00:00:00Z",
      row_count: 10, date_min: "2023-04-01", date_max: "2026-09-30", mines: ["SYN-A"], zones: ["SYN-A-Z1"],
      mine_zones: { "SYN-A": ["SYN-A-Z1"] }, rows_with_actual: 9, rows_pending_actual: 1, validation_status: "valid", sha256: "a",
    },
    {
      id: ZONES, kind: "exploration_zones", name: "Synthetic demonstration exploration zones", description: "", source_type: "synthetic",
      source_label: "SYNTHETIC DEMONSTRATION DATA", is_synthetic: true, deletable: false, created_at: "2026-10-09T00:00:00Z",
      row_count: 2, date_min: null, date_max: null, mines: [], zones: ["EZ-01", "EZ-02"], mine_zones: {}, rows_with_actual: 0,
      rows_pending_actual: 0, validation_status: "valid", sha256: "b",
    },
    {
      id: HOLES, kind: "drillholes", name: "Synthetic demonstration drillholes", description: "", source_type: "synthetic",
      source_label: "SYNTHETIC DEMONSTRATION DATA", is_synthetic: true, deletable: false, created_at: "2026-10-09T00:00:00Z",
      row_count: 11, date_min: null, date_max: null, mines: [], zones: ["EZ-01"], mine_zones: {}, rows_with_actual: 0,
      rows_pending_actual: 0, validation_status: "valid", sha256: "c",
    },
  ],
};

const band = {
  level: "high",
  label: "High",
  rule: "HIGH when the expected net gap to plan is at or below -5%.",
  thresholds: { high_at_or_below_pct: -5, medium_at_or_below_pct: -2 },
  expected_net_gap_pct: -10.8,
  value_kind: "rule_based",
};

const risk = {
  dataset: { id: DEMO, name: "x", source_type: "synthetic", source_label: "SYNTHETIC", is_synthetic: true, banner: "b", date_max: "2026-09-30", provenance: { source_type: "synthetic", label: "L", provider: "p", description: "d", url: null, licence: null, attribution: null, timestamp: null, limitations: [] } },
  scope: { mine_id: null, zone_id: null, label: "All mines and zones", key: "ALL__ALL" },
  horizon: { requested_days: 30, forecast_days: 30, start: "2026-10-01", end: "2026-10-30" },
  expected: { plan_t: 135408, forecast_t: 120775.8, net_gap_t: -14632.2, net_gap_pct: -10.81, gap_interval_low_t: -15096.8, gap_interval_high_t: -10396.3, interval_basis: "empirical", value_kind: "estimate", forecast_value_kind: "forecast" },
  shortfall_probability: { period_probability: 1, period_basis: "basis", mean_daily_probability: 0.91, daily_definition: "Material shortfall day", value_kind: "probability" },
  band,
  classification_check: { verdict: "beats_base_rate", text: "AUC 0.74 and Brier skill +2.9%.", roc_auc: 0.74, brier_skill_pct: 2.9, base_rate: 0.91, n: 224 },
  model_check: { regression_verdict: "beats_best_baseline", regression_text: "Beats.", classifier_verdict: "beats_base_rate" },
  drivers: [{ feature: "plan", label: "Planned tonnes for the day", importance_t: 120.5 }],
  limitations: ["Net gap is forecast plan minus forecast output."],
  source: "loaded",
};

const recommendations = {
  dataset: risk.dataset,
  scope: risk.scope,
  as_of: "2026-09-30",
  window_days: 28,
  recommendations: [
    {
      id: "REC-EQUIP-SYN-A-Z2", title: "Review recurring equipment downtime in zone SYN-A-Z2", priority: "medium", category: "maintenance",
      zone_id: "SYN-A-Z2", summary: "43% of zone-days had heavy downtime.", reasoning: "Repeated heavy-downtime days.",
      suggested_actions: ["Pull the breakdown log."], evidence: [{ metric: "Heavy days", value: 12, unit: "days", period: "p", value_kind: "measured" }],
      expected_impact: { status: "estimated", value_t: 1589, unit: "t", basis: "association basis" }, confidence: { level: "low", reasons: ["r"] },
      limitations: ["L"], value_kind: "rule_based",
    },
    {
      id: "REC-DATA-CAPTURE", title: "Close gaps in production data capture", priority: "medium", category: "data",
      zone_id: null, summary: "Only 80% have actuals.", reasoning: "Gaps.", suggested_actions: ["Check outages."],
      evidence: [{ metric: "Rows with an actual", value: 80, unit: "%", period: "p", value_kind: "measured" }],
      expected_impact: { status: "not_estimated", value_t: null, unit: "t", basis: "Data capture does not change tonnage." },
      confidence: { level: "low", reasons: ["r"] }, limitations: [], value_kind: "rule_based",
    },
  ],
  rules: [
    { rule_id: "equipment_recurrence", title: "Recurring equipment downtime", fired: true, reason: "Triggered.", checks: [] },
    { rule_id: "blasting_delay", title: "Blasting delays", fired: false, reason: "Below the trigger.", checks: [] },
  ],
  notes: ["Each recommendation cites evidence."],
};

const zonesFc = { type: "FeatureCollection", features: [] };
const exploration = {
  datasets: { zones: { id: ZONES, name: "z", source_type: "synthetic", source_label: "S", is_synthetic: true, row_count: 2 }, drillholes: { id: HOLES, name: "h", source_type: "synthetic", source_label: "S", is_synthetic: true, row_count: 11 } },
  banner: "SYNTHETIC DEMONSTRATION DATA. Zones are invented.",
  ranking_enabled: true,
  zones: [
    { zone_id: "EZ-01", name: "Demo zone 1", area_km2: 56.0, status: "observed", drillholes: 6, indicators: {}, indicator_rows: [
      { indicator: "host_unit_mapped", label: "Host unit mapped in zone (geological map)", value: 1, normalised: 1, weight: 0.2, evidence_class: "geological_map", available: true, value_kind: "measured" },
      { indicator: "mean_mn_pct", label: "Mean drillhole Mn grade (%)", value: 32.2, normalised: 1, weight: 0.4, evidence_class: "drilling", available: true, value_kind: "measured" },
      { indicator: "share_high_grade", label: "Share of intercepts at or above 20% Mn", value: 1, normalised: 1, weight: 0.4, evidence_class: "drilling", available: true, value_kind: "measured" },
    ], evidence_classes: ["drilling", "geological_map"], missing_inputs: [], score: 1, rank: 1, confidence: "medium", ranking_status: "ranked", ranking_reason: "Ranked on the available evidence.", value_kind: "index" },
    { zone_id: "EZ-02", name: "Demo zone 2", area_km2: 54.9, status: "inferred", drillholes: 0, indicators: {}, indicator_rows: [], evidence_classes: ["geological_map"], missing_inputs: ["Mean drillhole Mn grade (%)"], score: null, rank: null, confidence: "low", ranking_status: "not_ranked", ranking_reason: "Only 1 evidence class.", value_kind: "index" },
  ],
  method: { weights: { host_unit_mapped: 0.2, mean_mn_pct: 0.4, share_high_grade: 0.4 }, high_grade_cutoff_pct: 20, min_zones_to_rank: 3, min_evidence_classes_to_rank: 2, description: "Index description. Not a probability or a reserve estimate.", context_not_scored: ["NDVI"], context_reason: "Context reason." },
  required_inputs: ["Geological map."],
  notes: [],
};

const layers = { aoi_bbox: [80.0, 21.7, 80.4, 22.0], layers: [{ id: "zones", label: "z", is_synthetic: true, note: "n" }], attribution: { basemap: "Natural Earth" } };

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function route(overrides: Record<string, () => Response> = {}) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = new URL(String(input), "http://localhost");
    const key = url.pathname;
    if (overrides[key]) return overrides[key]();
    const table: Record<string, unknown> = {
      "/api/datasets": datasets,
      "/api/risk": risk,
      "/api/recommendations": recommendations,
      "/api/exploration": exploration,
      "/api/geo/layers": layers,
      "/api/geo/layers/aoi": zonesFc,
      "/api/geo/layers/mines": zonesFc,
      "/api/geo/layers/zones": zonesFc,
    };
    if (key in table) return json(table[key]);
    return json({ error: { code: "not_found", message: "Not found" } }, 404);
  });
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("shortfall risk page", () => {
  it("shows the rule-based band and keeps the expected gap labelled as an estimate", async () => {
    route();
    render(<DatasetProvider><RiskPage /></DatasetProvider>);
    const bandEl = await screen.findByTestId("risk-band");
    expect(bandEl).toHaveTextContent("HIGH");
    expect(screen.getByText(/Rule-based/)).toBeInTheDocument();
    expect(screen.getByText(/Probability the period ends below plan/)).toBeInTheDocument();
    expect(screen.getByText(/Net gap is forecast plan minus forecast output/)).toBeInTheDocument();
  });
});

describe("recommendations page", () => {
  it("separates estimated impacts from not-estimated ones and lists rules checked", async () => {
    route();
    render(<DatasetProvider><RecommendationsPage /></DatasetProvider>);
    expect(await screen.findByText("Review recurring equipment downtime in zone SYN-A-Z2")).toBeInTheDocument();
    expect(screen.getByText("ESTIMATED")).toBeInTheDocument();
    expect(screen.getByText("Not estimated", { exact: false })).toBeInTheDocument();
    const rules = screen.getByRole("table", { name: /Recommendation rules/ });
    expect(within(rules).getByText("Triggered")).toBeInTheDocument();
    expect(within(rules).getByText("Not triggered")).toBeInTheDocument();
  });

  it("shows an explicit empty state when nothing fires", async () => {
    route({
      "/api/recommendations": () => json({ ...recommendations, recommendations: [] }),
    });
    render(<DatasetProvider><RecommendationsPage /></DatasetProvider>);
    expect(await screen.findByText("No action is recommended on the current evidence.")).toBeInTheDocument();
  });
});

describe("geospatial view", () => {
  it("lists zones with evidence status and shows the selected zone's indicators", async () => {
    route();
    render(<DatasetProvider><MapPage /></DatasetProvider>);
    const list = await screen.findByRole("button", { name: /EZ-01/ });
    expect(list).toHaveTextContent("Rank 1");
    expect(screen.getByRole("button", { name: /EZ-02/ })).toHaveTextContent("Not ranked");
    fireEvent.click(screen.getByRole("button", { name: /EZ-02/ }));
    expect(await screen.findByText("Only 1 evidence class.")).toBeInTheDocument();
    expect(screen.getByText("Missing inputs (not imputed)")).toBeInTheDocument();
    expect(screen.getByTestId("map-stub")).toBeInTheDocument();
  });

  it("shows the synthetic banner for the demonstration zones", async () => {
    route();
    render(<DatasetProvider><MapPage /></DatasetProvider>);
    await screen.findByRole("button", { name: /EZ-01/ });
    expect(screen.getByText("SYNTHETIC DEMONSTRATION DATA")).toBeInTheDocument();
  });
});

describe("reports page", () => {
  it("posts the selected sections and reports a successful download", async () => {
    const bodies: unknown[] = [];
    const spy = route();
    spy.mockImplementation(async (input, init) => {
      const url = new URL(String(input), "http://localhost");
      if (url.pathname === "/api/reports") {
        bodies.push(JSON.parse(String(init?.body)));
        return new Response("<html></html>", {
          status: 200,
          headers: { "Content-Type": "text/html", "Content-Disposition": 'attachment; filename="report.html"' },
        });
      }
      if (url.pathname === "/api/datasets") return json(datasets);
      return json({ error: { code: "not_found", message: "Not found" } }, 404);
    });
    global.URL.createObjectURL = vi.fn(() => "blob:test");
    global.URL.revokeObjectURL = vi.fn();
    render(<DatasetProvider><ReportsPage /></DatasetProvider>);
    const boxes = await screen.findAllByRole("checkbox");
    fireEvent.click(boxes[0]!); // untick overview
    fireEvent.click(screen.getByRole("button", { name: "Generate and download" }));
    await waitFor(() => expect(bodies.length).toBe(1));
    const body = bodies[0] as { sections: string[]; format: string; dataset_id: string };
    expect(body.sections).not.toContain("overview");
    expect(body.format).toBe("html");
    expect(body.dataset_id).toBe(DEMO);
    expect(await screen.findByText(/Downloaded report.html/)).toBeInTheDocument();
  });
});
