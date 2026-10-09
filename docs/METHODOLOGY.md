# Methodology

This document says exactly what each number in MineMind AI is, how it was computed, and what it cannot support. Code references are to `backend/app/domain/`.

## 1. Measured values

* **Planned and actual tonnes, delay hours, rainfall.** Taken from the stored dataset (`kpis.py`).
* **Matched days.** Only rows with both a plan and an actual enter the gap, variance and attainment figures. Pending rows are counted and reported, never filled.
* **Gap (t)** = Σ actual − Σ plan over matched days. **Variance (%)** = gap ÷ Σ plan. **Attainment (%)** = Σ actual ÷ Σ plan.
* **Days below plan (%)**: share of matched rows with actual < plan.
* **Coverage (%)**: share of rows in the selection with an actual value.
* **Heavy-constraint day**: a zone-day with equipment downtime above 8 h, weather delay above 6 h, or blasting delay above 4 h. Thresholds are policy (`policy.py`).
* **Freshness**: days between the as-of date (today, UTC) and the latest actual. Stale when above the threshold (default 14 days).

## 2. Validation rules (production.v1)

Blocking errors: missing required columns (`date`, `mine_id`, `zone_id`, `planned_production_t`, `actual_production_t`); invalid dates; non-numeric or negative values; hours above 24; blank plan; duplicate date/mine/zone keys; more rows than the limit; non-UTF-8 or unreadable files.

Warnings (accepted): pending actuals; unknown columns (ignored); calendar gaps inside a series (not filled); actual above 2.5 times plan; future-dated actuals; rainfall above 500 mm/day; IQR outliers (3 times the IQR within each mine/zone series), flagged and kept unchanged.

## 3. Forecasting

### 3.1 Daily series and scope

For a scope (all mines, a mine, or a zone) the table is aggregated to one row per calendar day:

* `plan` = Σ planned tonnes on that day (planned values are required on every row).
* `actual` = Σ actual tonnes **only on days where every zone row has an actual**. A day with a missing zone actual is missing, not understated.
* Operational hours are averaged per zone-day, so the units do not change with scope size.

### 3.2 Features (leakage rules)

For day *t*, every feature uses information dated before *t*, except two inputs known in advance:

* `plan_t`, the planned tonnes for *t*;
* calendar terms (day-of-week and day-of-year sine and cosine).

Features: actuals at lags 1, 2 and 7; means of the last 7 and 28 actual days; attainment over the last 7 days; lag-1 and 7-day means of downtime, weather delay, blasting delay and rainfall. **Same-day operational values are never features.** The test suite checks that perturbing day *t*'s target or operational values leaves *t*'s features unchanged, and that perturbing any later day leaves earlier features unchanged.

### 3.3 Universe, split and backtest

* **Universe**: days with an actual, a plan, and lag-1, lag-7 and 7-day-mean features. Every model and baseline is scored on the same days.
* **Folds**: expanding window. The default is 3 test windows of 90 days, the last ending on the final labelled day. Each fold trains only on days strictly before its window.
* **Minimum data**: at least 180 training days per fold. Otherwise the request fails with `insufficient_data` (422), stating the days found and the days required.
* **No shuffling** anywhere.

### 3.4 Baselines and models

| Method | Definition |
| --- | --- |
| Plan | forecast = planned tonnes that day |
| Persistence | forecast = actual yesterday |
| Seasonal naive | forecast = actual on the same weekday last week |
| Moving average | forecast = mean of the last 7 actual days |
| Ridge (benchmark) | standardised features, median imputation, α = 1 |
| **Gradient boosting (forecast model)** | HistGradientBoostingRegressor, 250 iterations, learning rate 0.05, 15 leaves, min 20 samples per leaf, L2 = 1, fixed random state |

The gradient boosting model was specified before the backtest was run. Ridge is reported as a benchmark. When ridge has lower backtest MAE, the verdict text says so, and the forecast still uses gradient boosting. Choosing the better model after seeing the test results would bias the comparison.

### 3.5 Metrics and comparison

* **MAE** = mean |actual − forecast| (t/day). **RMSE** = √mean (actual − forecast)². Both are reported per fold and pooled.
* **Gap to the best baseline**: the mean difference in absolute error between the gradient boosting model and the lowest-MAE baseline, with a **moving-block bootstrap 95% interval** (1,000 resamples, 7-day blocks, fixed seed). The verdict is:
  * *beats the best baseline* if the whole interval is below zero;
  * *worse than the best baseline* if it is above zero;
  * *no reliable difference* otherwise.
* **Skill** (point estimate) = 1 − MAE_model ÷ MAE_best_baseline.

### 3.6 Forward forecast

Recursive, one day at a time. Each predicted day becomes the "actual" used for later lags. Operational inputs for future days are **scenario assumptions**, held at their trailing 28-day means, and the response says so. If a future day has no planned tonnage, the horizon stops there and the reason is reported.

### 3.7 Intervals

* **Per-day band**: forecast + the 10th and 90th percentiles of pooled out-of-sample residuals. Empirical, not calibrated, and it does not widen with horizon.
* **Net gap** (Σ forecast − Σ plan over the horizon) with an interval from the 10th and 90th percentiles of every backtest window of the same length (overlapping windows, at least 70% of days present, totals scaled by the window length). Reported only when at least 20 windows exist.
* **Probability the period ends below plan**: the share of those backtest windows in which the realised gap was below plan, given the forecast net gap. This is an empirical frequency, not a model probability.

### 3.8 Shortfall classification

* **Target**: a *material shortfall day*, meaning actual output below 95% of plan (`SHORTFALL_DAY_TOLERANCE_PCT = 5`). A day merely a few tonnes below plan is not a shortfall for this purpose.
* **Model**: logistic regression on the same features, with median imputation and standardisation.
* **Metrics**: base rate, ROC AUC, Brier score, Brier skill against a climatology forecast (the training base rate), and calibration in quintiles. AUC is reported as not evaluable when the test window has one class.
* **Verdict**: *beats base rate* when Brier skill is positive, *no skill over base rate* otherwise. Reported in the UI and in the risk payload.

### 3.9 Drivers

* **Forecast drivers**: permutation importance on the last backtest fold, using that fold's model and that fold's held-out data. It measures reliance, not cause.
* **Shortfall drivers**: standardised logistic coefficients on all labelled days. They describe associations in this dataset.

### 3.10 Persistence

Each scope's model is saved with its fingerprint (SHA-256 of the scope's rows and the configuration), the configuration hash, library versions and metrics. A request reuses the model only when the fingerprint and configuration match and the scikit-learn version is the same. Otherwise it retrains and overwrites. The test suite checks save, reload, identical predictions, invalidation on changed data, and refusal of non-model files.

## 4. Shortfall risk

* **Expected net gap** = Σ forecast − Σ plan (tonnes and % of plan). Negative means shortfall. Labelled *estimate*, because it is arithmetic on a forecast.
* **Band** (*rule-based*, not learned): **HIGH** when the expected net gap is at or below −5% of plan; **MEDIUM** at or below −2%; otherwise **LOW**. If no forecast can be produced, the band is "not assessed".
* The daily classifier and the period probability are reported beside the band. They do not set it.

## 5. Recommendations

Eight rules plus a data-freshness check. Each rule has a stated trigger, cites its evidence (metric, value, unit, period, value type), and states an expected impact:

| Rule | Trigger (policy thresholds in `policy.py`) | Impact |
| --- | --- | --- |
| Recurring equipment downtime | At least 30% of the zone's last 28 days above 8 h downtime | **Estimated**: (mean output on normal days − mean output on heavy days, from that zone's history) × heavy days in the window. Association, not causal. |
| Persistent shortfall | Attainment below 97% and at least 60% of matched days below plan (last 28 days) | Not estimated |
| Monsoon weather exposure | June–September weather delay at least 1.5 times the rest of the year | Not estimated |
| Blasting delays | Mean blasting delay at least 1 h per zone-day (last 90 days); names the worst weekday | Not estimated |
| Shortfall concentrated in one zone | One zone carries at least 50% of shortfall tonnes | Not estimated |
| Missing actuals | Less than 95% of rows in the window have actuals | Not estimated |
| Forecast gap | Forecast band HIGH or MEDIUM with a negative net gap | **Estimated** size of the gap and the uplift per day (arithmetic). Not a forecast of what an action would recover. |
| Forecast reliability | Regression does not beat the best baseline, or the classifier has no skill | Not estimated |
| Stale data | Latest actual older than the freshness threshold | Not estimated |

Rules that do not fire are listed with their reason, so an empty list is never silent. Windows end on the last day with any recorded data, so a stretch of missing actuals is seen by the completeness rule rather than hidden by moving the window earlier.

## 6. Exploration zone prioritisation

**What it is.** An index that orders zones by the strength of *geological and drilling evidence* for where to investigate first. It is not a probability of mineralisation, not a resource estimate and not a reserve.

**Scored indicators (weights):**

* host lithology mapped in the zone, from the (user-supplied) geological map: 0.2;
* mean drillhole Mn grade (%): 0.4;
* share of drillhole intercepts at or above a 20% Mn cut-off: 0.4.

**Context only, never scored:** vegetation indices, rainfall, soil moisture, land-surface temperature, and SAR backscatter. These respond to many non-mineral processes. Using them as evidence would present vegetation or moisture as proof of manganese, which the data does not support.

**Procedure:**

1. Each indicator is min-max normalised across zones with data (0 to 1). If all zones share one value, the normalised value is 1.
2. The index is the weighted mean of the zone's available normalised indicators, with weights renormalised over those available. A missing input is listed and is **not** imputed.
3. **Gating.** A zone is ranked only if it has at least two evidence classes (geological map and drilling) and at least three zones with comparable data exist. Otherwise it is shown with its indicators and a reason, without a rank.
4. Confidence: medium when there are two evidence classes and at least five drillholes; otherwise low.

**Status**: *observed* (drilling present), *inferred* (host unit mapped, no drilling), *host unit not mapped*, or *unavailable*.

**Required before any real assessment** (also shown in the app): a geological map by a geologist; drillhole collars, depths, assays and QA/QC; known occurrences and mine records (for proximity tests and calibration); field observations of surface manganese; DEM and structure if slope or lineament indicators are used; and validation with spatial cross-validation before any ranking informs drilling.

**Demonstration data.** The six synthetic zones (EZ-01 to EZ-06), their host-unit flags and the drillhole grades are invented. Four zones have drilling, two do not. The demonstration exists to show the gates working: two zones are correctly left unranked.

## 7. Reports

Every section names its value type and source. The top of every report carries the synthetic notice when the dataset is synthetic. All user-supplied text is HTML-escaped. The JSON format carries the same fields with a `value_type_legend`.

## 8. Limits of these methods

* Patterns in synthetic data reflect the generator. Backtest results describe the synthetic data only.
* Forecasts are conditional on the scenario inputs. Real operating conditions (grade variation, fleet availability, staffing, planned shutdowns) are not in the data and cannot be explained by the models.
* Intervals and period probabilities are empirical summaries of a few hundred backtest days. They are not calibrated predictive distributions.
* Thresholds are policy choices. Changing them changes the bands and the rules; they are visible in `policy.py` for review.
