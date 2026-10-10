/** Types for the exploration (zone prioritisation) API. Mirrors backend/app/api/routes/exploration.py. */

export interface ExplorationIndicatorRow {
  indicator: "host_unit_mapped" | "mean_mn_pct" | "share_high_grade";
  label: string;
  value: number | null;
  normalised: number | null;
  weight: number;
  evidence_class: string;
  available: boolean;
  value_kind: "measured";
}

export interface ExplorationZone {
  zone_id: string;
  name: string;
  area_km2: number | null;
  status: "observed" | "inferred" | "host_unit_not_mapped" | "unavailable";
  drillholes: number;
  indicators: Record<string, number | null>;
  indicator_rows: ExplorationIndicatorRow[];
  evidence_classes: string[];
  missing_inputs: string[];
  score: number | null;
  rank: number | null;
  confidence: "low" | "medium";
  ranking_status: "ranked" | "not_ranked";
  ranking_reason: string;
  value_kind: "index";
}

export interface ExplorationDatasetContext {
  id: string;
  name: string;
  source_type: string;
  source_label: string;
  is_synthetic: boolean;
  row_count: number;
}

export interface ExplorationResponse {
  datasets: { zones: ExplorationDatasetContext; drillholes: ExplorationDatasetContext };
  banner: string | null;
  ranking_enabled: boolean;
  zones: ExplorationZone[];
  method: {
    weights: Record<string, number>;
    high_grade_cutoff_pct: number;
    min_zones_to_rank: number;
    min_evidence_classes_to_rank: number;
    description: string;
    context_not_scored: string[];
    context_reason: string;
  };
  required_inputs: string[];
  notes: string[];
}
