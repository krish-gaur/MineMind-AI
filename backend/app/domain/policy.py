"""Policy constants: every threshold used by rules, bands and gates lives here.

These are *operational policy choices*, not learned parameters. They are shown
to users wherever they are applied, so a reviewer can challenge or change them.
"""

from __future__ import annotations

# --- day-level "heavy constraint" thresholds (hours lost in one zone-day) ---
DOWNTIME_HEAVY_DAY_H = 8.0
WEATHER_HEAVY_DAY_H = 6.0
BLASTING_HEAVY_DAY_H = 4.0

# --- recommendation rules ---------------------------------------------------
RECENT_WINDOW_DAYS = 28
RECURRENCE_SHARE_PCT = 30.0  # heavy-downtime days in the recent window before a recurrence flag
ATTAINMENT_TARGET_PCT = 97.0  # below this, a production deviation is investigated
SHORTFALL_DAYS_SHARE_PCT = 60.0  # share of days below plan before the deviation is "persistent"
WEATHER_MONSOON_RATIO = 1.5  # monsoon vs non-monsoon weather-delay ratio that prompts review
BLASTING_MEAN_H_PER_DAY = 1.0  # average blasting delay per zone-day that prompts review
DATA_COMPLETENESS_MIN_PCT = 95.0  # below this share of rows with actuals, data capture is flagged
ZONE_GAP_CONCENTRATION_PCT = 50.0  # share of shortfall tonnes in one zone that is flagged

# --- risk bands (applied to model outputs; see docs/METHODOLOGY.md) ---------
RISK_HIGH_SHORTFALL_PCT = 5.0  # expected net shortfall (% of plan) at or above which risk is HIGH
RISK_MEDIUM_SHORTFALL_PCT = 2.0
RISK_HIGH_PROBABILITY = 0.75  # mean daily shortfall probability at or above which risk is HIGH
RISK_MEDIUM_PROBABILITY = 0.60

# --- forecasting data requirements -------------------------------------------
MIN_TRAIN_DAYS = 180  # labelled days needed before training is attempted
BACKTEST_FOLDS = 3
BACKTEST_TEST_DAYS = 90
MIN_CLASS_ROWS = 30  # per class needed for AUC and calibration checks

# --- exploration -----------------------------------------------------------
MIN_EVIDENCE_CLASSES_TO_RANK = 2
MIN_ZONES_TO_RANK = 3
