/** API response types. These mirror the Pydantic models in backend/app/schemas. */

export type SourceType = "synthetic" | "user_provided" | "public";

export type ValueKind =
  | "measured"
  | "forecast"
  | "probability"
  | "estimate"
  | "scenario"
  | "rule_based"
  | "index";

export interface Provenance {
  source_type: SourceType;
  label: string;
  provider: string;
  description: string;
  url: string | null;
  licence: string | null;
  attribution: string | null;
  timestamp: string | null;
  limitations: string[];
}

export interface ValidationIssue {
  severity: "error" | "warning";
  code: string;
  message: string;
  affected_rows: number;
  examples: string[];
}

export interface ColumnProfile {
  name: string;
  present: boolean;
  required: boolean;
  unit: string;
  missing_count: number;
  missing_pct: number | null;
  min: number | null;
  max: number | null;
  mean: number | null;
  outlier_count: number;
  outlier_rule: string | null;
}

export interface ValidationReport {
  status: "valid" | "valid_with_warnings" | "invalid";
  schema_version: string;
  row_count: number;
  issues: ValidationIssue[];
  columns: ColumnProfile[];
  unknown_columns: string[];
  date_min: string | null;
  date_max: string | null;
  series_count: number;
  mines: string[];
  zones: string[];
  rows_with_actual: number;
  rows_pending_actual: number;
  missing_date_gaps: number;
  generated_at: string;
}

export interface DatasetSummary {
  id: string;
  kind: "production" | "drillholes" | "exploration_zones";
  name: string;
  description: string;
  source_type: SourceType;
  source_label: string;
  is_synthetic: boolean;
  deletable: boolean;
  created_at: string;
  row_count: number;
  date_min: string | null;
  date_max: string | null;
  mines: string[];
  zones: string[];
  rows_with_actual: number;
  rows_pending_actual: number;
  validation_status: string | null;
  sha256: string;
}

export interface DatasetList {
  datasets: DatasetSummary[];
}

export interface DatasetDetail extends DatasetSummary {
  provenance: Provenance;
  validation: ValidationReport | null;
  original_filename: string | null;
  size_bytes: number;
  generator: Record<string, unknown> | null;
}

export interface DatasetPreview {
  dataset_id: string;
  total_rows: number;
  returned_rows: number;
  columns: string[];
  rows: Record<string, string | number | null>[];
}

export interface ProductionColumnDoc {
  name: string;
  required: boolean;
  type: string;
  unit: string;
  description: string;
  min_value: number | null;
  max_value: number | null;
}

export interface ProductionSchema {
  schema_version: string;
  columns: ProductionColumnDoc[];
  max_upload_mb: number;
  max_upload_rows: number;
  accepted_extensions: string[];
  example_csv: string;
}

export interface OverviewKpis {
  planned_t: number | null;
  actual_t: number | null;
  gap_t: number | null;
  variance_pct: number | null;
  attainment_pct: number | null;
  coverage_pct: number | null;
  days_below_plan_pct: number | null;
  equipment_downtime_h_total: number | null;
  equipment_downtime_h_per_zone_day: number | null;
  equipment_downtime_days_over_threshold_pct: number | null;
  value_kind: ValueKind;
}

export interface ConstraintItem {
  key: string;
  label: string;
  column: string;
  total_hours: number | null;
  share_pct: number | null;
  mean_hours_per_zone_day: number | null;
  records: number;
  threshold_hours: number;
  days_over_threshold: number;
  value_kind: ValueKind;
}

export interface MonthlyPoint {
  month: string;
  planned_t: number | null;
  actual_t: number | null;
  gap_t: number | null;
  attainment_pct: number | null;
  records_with_actual: number;
  equipment_downtime_h_mean: number | null;
}

export interface ZoneSummary {
  mine_id: string;
  zone_id: string;
  records: number;
  pending_rows: number;
  planned_t: number | null;
  actual_t: number | null;
  gap_t: number | null;
  variance_pct: number | null;
  attainment_pct: number | null;
  equipment_downtime_h_total: number | null;
  weather_delay_h_total: number | null;
  blasting_delay_h_total: number | null;
}

export interface Freshness {
  last_actual_date: string | null;
  days_since_last_actual: number | null;
  stale_threshold_days: number;
  status: "fresh" | "stale" | "unknown";
  as_of: string;
}

export interface OverviewResponse {
  dataset: {
    id: string;
    name: string;
    source_type: SourceType;
    source_label: string;
    is_synthetic: boolean;
    banner: string | null;
  };
  filters: {
    start: string | null;
    end: string | null;
    mine_id: string | null;
    zone_id: string | null;
  };
  empty: boolean;
  period: {
    start: string | null;
    end: string | null;
    days: number;
    rows: number;
    rows_with_actual: number;
    rows_pending_actual: number;
    series: number;
  };
  kpis: OverviewKpis;
  constraints: ConstraintItem[];
  monthly: MonthlyPoint[];
  zones: ZoneSummary[];
  freshness: Freshness;
  provenance: Provenance;
  notes: string[];
}

export interface DataSourceEntry {
  id: string;
  name: string;
  provider: string;
  source_type: SourceType;
  url: string;
  access: string;
  licence: string;
  attribution: string;
  used_for: string;
  limitations: string[];
}

export interface SourcesResponse {
  sources: DataSourceEntry[];
}
