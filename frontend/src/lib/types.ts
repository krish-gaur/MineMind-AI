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
  mine_zones: Record<string, string[]>;
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

/* ---------------- Forecasting, risk and recommendations ---------------- */

export interface ScopeInfo {
  mine_id: string | null;
  zone_id: string | null;
  label: string;
  key: string;
}

export interface ForecastModelCard {
  name: string;
  regressor: string;
  classifier: string;
  value_kind: "forecast";
  source: "memory" | "loaded" | "trained";
  model_version: string;
  fingerprint: string;
  trained_at: string;
  trained_on: { labelled_days: number; first_day: string; last_actual_day: string };
  features: string[];
  config: Record<string, number>;
  versions: Record<string, string>;
  random_state: number;
}

export interface ModelMetric {
  name: string;
  label: string;
  kind: "model" | "baseline";
  mae: number;
  rmse: number;
  n: number;
}

export interface FoldInfo {
  fold: number;
  train_end: string;
  test_start: string;
  test_end: string;
  train_days: number;
  test_days: number;
  gradient_boosting_mae: number;
}

export interface GapToBaseline {
  mae_difference: number;
  ci95_low: number;
  ci95_high: number;
  skill_pct_vs_best_baseline: number | null;
  bootstrap: string;
}

export interface ClassificationEvaluation {
  target: string;
  model: string;
  n: number;
  base_rate: number;
  roc_auc: number | null;
  brier: number;
  brier_climatology: number;
  brier_skill_pct: number | null;
  calibration: { bin: string; n: number; mean_predicted: number; observed_rate: number }[];
  verdict: "beats_base_rate" | "no_skill_over_base_rate" | "not_evaluable";
  verdict_text: string;
  value_kind: "probability";
}

export interface ForecastEvaluation {
  method: string;
  evaluation_start: string;
  evaluation_end: string;
  n_evaluated_days: number;
  folds: FoldInfo[];
  models: ModelMetric[];
  per_fold: Record<string, number>[];
  mae_by_fold: Record<string, { mean: number; std: number }>;
  best_baseline: string;
  gap_to_best_baseline: GapToBaseline;
  verdict: "beats_best_baseline" | "worse_than_best_baseline" | "no_reliable_difference";
  verdict_text: string;
  residual_q10_t: number;
  residual_q90_t: number;
  model_labels: Record<string, string>;
}

export interface HistoryPoint {
  date: string;
  actual_t: number | null;
  plan_t: number | null;
  gradient_boosting_t: number | null;
  ridge_t: number | null;
  seasonal_naive_7_t: number | null;
  shortfall_probability: number | null;
}

export interface ForecastDay {
  date: string;
  plan_t: number;
  forecast_t: number;
  interval_low_t: number;
  interval_high_t: number;
  shortfall_probability: number;
}

export interface ForecastTotals {
  plan_t: number;
  forecast_t: number;
  net_gap_t: number;
  net_gap_pct: number | null;
  gap_interval_low_t: number | null;
  gap_interval_high_t: number | null;
  interval_basis: string;
  period_shortfall_probability: number | null;
  mean_daily_shortfall_probability: number;
  start: string;
  end: string;
}

export interface ForecastBlock {
  requested_days: number;
  forecast_days: number;
  truncated_reason: string | null;
  scenario_assumptions: {
    window_days: number;
    values: Record<string, number>;
    description: string;
  };
  days: ForecastDay[];
  totals: ForecastTotals | null;
}

export interface ForecastResponse {
  dataset: DatasetContext;
  scope: ScopeInfo;
  model: ForecastModelCard;
  evaluation: ForecastEvaluation;
  classification: ClassificationEvaluation;
  backtest_history: HistoryPoint[];
  forecast: ForecastBlock;
  drivers: {
    forecast_drivers: { feature: string; label: string; importance_t: number }[];
    forecast_drivers_method: string | null;
    shortfall_coefficients: {
      feature: string;
      label: string;
      standardised_coefficient: number;
      direction: string;
    }[];
    shortfall_method: string;
  };
  value_kinds: Record<string, string>;
  notes: string[];
}

export interface DatasetContext {
  id: string;
  name: string;
  source_type: SourceType;
  source_label: string;
  is_synthetic: boolean;
  banner: string | null;
  date_max: string | null;
  provenance: Provenance;
}

export interface RiskResponse {
  dataset: DatasetContext;
  scope: ScopeInfo;
  horizon: { requested_days: number; forecast_days: number; start: string | null; end: string | null };
  expected: {
    plan_t: number;
    forecast_t: number;
    net_gap_t: number;
    net_gap_pct: number | null;
    gap_interval_low_t: number | null;
    gap_interval_high_t: number | null;
    interval_basis: string;
    value_kind: "estimate";
    forecast_value_kind: "forecast";
  } | null;
  shortfall_probability: {
    period_probability: number | null;
    period_basis: string;
    mean_daily_probability: number;
    daily_definition: string;
    value_kind: "probability";
  } | null;
  band: {
    level: "high" | "medium" | "low" | "insufficient_data";
    label: string;
    rule: string;
    thresholds: { high_at_or_below_pct: number; medium_at_or_below_pct: number };
    expected_net_gap_pct: number | null;
    value_kind: "rule_based";
  };
  classification_check: {
    verdict: string;
    text: string;
    roc_auc: number | null;
    brier_skill_pct: number | null;
    base_rate: number;
    n: number;
  } | null;
  model_check: {
    regression_verdict: string;
    regression_text: string;
    classifier_verdict: string;
  } | null;
  drivers: { feature: string; label: string; importance_t: number }[];
  limitations: string[];
  source: "memory" | "loaded" | "trained";
}

export interface EvidenceItem {
  metric: string;
  value: string | number | null;
  unit: string;
  period: string;
  value_kind: string;
}

export interface RecommendationItem {
  id: string;
  title: string;
  priority: "high" | "medium" | "low";
  category: string;
  zone_id: string | null;
  summary: string;
  reasoning: string;
  suggested_actions: string[];
  evidence: EvidenceItem[];
  expected_impact: {
    status: "estimated" | "not_estimated";
    value_t: number | null;
    unit: string;
    basis: string;
  };
  confidence: { level: "low" | "medium"; reasons: string[] };
  limitations: string[];
  value_kind: "rule_based";
}

export interface RuleOutcome {
  rule_id: string;
  title: string;
  fired: boolean;
  reason: string;
  checks: Record<string, unknown>[];
}

export interface RecommendationsResponse {
  dataset: DatasetContext;
  scope: ScopeInfo;
  as_of: string | null;
  window_days: number;
  recommendations: RecommendationItem[];
  rules: RuleOutcome[];
  notes: string[];
}
