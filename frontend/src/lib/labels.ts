/** Wording shared across pages. Keep these consistent with backend/app/domain/provenance.py. */

export const SYNTHETIC_BANNER =
  "Not MOIL operational records. Figures show how the workflow behaves and are not evidence of real production performance.";

export const VALUE_KIND_HELP: Record<string, string> = {
  measured: "Recorded in the dataset. Not modelled.",
  forecast: "Output of a regression model trained on the dataset.",
  probability: "Output of a classifier. Calibration is reported separately.",
  estimate: "Arithmetic on stated assumptions. Not a measurement.",
  scenario: "Projection under a stated assumption.",
  rule_based: "Transparent policy thresholds. Not learned from data.",
  index: "Weighted combination of indicators. Not a probability or a reserve estimate.",
};

/** Mirrors ATTAINMENT_TARGET_PCT in backend/app/domain/policy.py (policy choice, not learned). */
export const ATTAINMENT_TARGET_PCT = 97;
/** Mirrors DOWNTIME_HEAVY_DAY_H in backend/app/domain/policy.py. */
export const DOWNTIME_HEAVY_DAY_H = 8;
