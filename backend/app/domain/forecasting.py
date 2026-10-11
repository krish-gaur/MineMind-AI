"""Production forecasting: baselines, a gradient-boosting regressor, time-ordered backtests.

Method (see docs/METHODOLOGY.md)
--------------------------------
1. **Universe.** Days with a recorded actual and complete lag history (lags 1, 7 and the
   7-day mean), so every baseline and model is scored on the *same* days.
2. **Baselines first.** Plan, persistence, seasonal naive (same weekday last week) and a
   7-day moving average. A model is only worth keeping if it beats the best of these.
3. **Backtest.** Expanding-window, time-ordered folds (default 3 x 90 days). Each fold trains
   only on days strictly before its test window. No shuffling.
4. **Metrics.** MAE and RMSE per model and per fold, plus pooled out-of-sample metrics.
   The gap to the best baseline is reported with a moving-block bootstrap 95% interval.
5. **Final model.** Refit on all universe days. Future days are forecast recursively. Operational
   inputs for future days are explicit scenario assumptions (trailing 28-day means).
6. **Shortfall classification** is a separate, explicit logistic model: P(actual < plan) for a day.
7. **Persistence.** Models are saved with a data fingerprint and a configuration hash and are
   reloaded only when both still match. Pickled artefacts must come from this application only.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from app.domain import policy
from app.domain.features import Scope, build_features, feature_names, scope_rows
from app.errors import InsufficientDataError

MODEL_VERSION = "forecast-v1"
RANDOM_STATE = 26009
BASELINE_KEYS: tuple[str, ...] = ("plan", "persistence", "seasonal_naive_7", "moving_average_7")
BASELINE_LABELS: dict[str, str] = {
    "plan": "Plan (the planned tonnage is the forecast)",
    "persistence": "Persistence (yesterday's actual)",
    "seasonal_naive_7": "Seasonal naive (same weekday last week)",
    "moving_average_7": "Moving average (mean of last 7 days)",
}
MODEL_KEYS: tuple[str, ...] = ("gradient_boosting", "ridge")
MODEL_LABELS: dict[str, str] = {
    "gradient_boosting": "Gradient boosting regressor (scikit-learn HistGradientBoosting)",
    "ridge": "Ridge regression (linear benchmark)",
}
BOOTSTRAP_RESAMPLES = 1000
BOOTSTRAP_BLOCK_DAYS = 7
SCENARIO_WINDOW_DAYS = 28


@dataclass(frozen=True)
class TrainingConfig:
    test_days: int = policy.BACKTEST_TEST_DAYS
    folds: int = policy.BACKTEST_FOLDS
    min_train_days: int = policy.MIN_TRAIN_DAYS
    horizon_days: int = 30

    def as_dict(self) -> dict[str, int]:
        return {
            "test_days": self.test_days,
            "folds": self.folds,
            "min_train_days": self.min_train_days,
            "horizon_days": self.horizon_days,
        }


def config_hash(config: TrainingConfig) -> str:
    payload = json.dumps(
        {
            "model_version": MODEL_VERSION,
            "random_state": RANDOM_STATE,
            "sklearn": sklearn.__version__,
            "config": config.as_dict(),
            "policy": {"min_class_rows": policy.MIN_CLASS_ROWS},
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def scope_fingerprint(frame: pd.DataFrame, scope: Scope, config: TrainingConfig) -> str:
    rows = scope_rows(frame, scope).sort_values(["date", "mine_id", "zone_id"])
    digest = hashlib.sha256()
    digest.update(rows.to_csv(index=False, float_format="%.6f", na_rep="").encode("utf-8"))
    digest.update(config_hash(config).encode())
    return digest.hexdigest()[:32]


# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------
def make_gradient_boosting() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=250,
        learning_rate=0.05,
        max_leaf_nodes=15,
        min_samples_leaf=20,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=RANDOM_STATE,
    )


def make_ridge() -> Pipeline:
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=1.0))


def make_shortfall_classifier() -> Pipeline:
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=1.0, max_iter=2000, random_state=RANDOM_STATE),
    )


# ----------------------------------------------------------------------------
# Data preparation and folds
# ----------------------------------------------------------------------------
def prepare_universe(series: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Return (universe rows with features and targets, feature names)."""
    names = feature_names(series)
    feats = build_features(series)
    frame = feats.copy()
    frame["actual"] = series["actual"]
    threshold = series["plan"] * (1.0 - policy.SHORTFALL_DAY_TOLERANCE_PCT / 100.0)
    frame["short"] = (series["actual"] < threshold).astype(float).where(series["actual"].notna())
    frame["base_plan"] = feats["plan"]
    frame["base_persistence"] = feats["act_lag1"]
    frame["base_seasonal_naive_7"] = feats["act_lag7"]
    frame["base_moving_average_7"] = feats["act_roll7"]
    mask = (
        frame["actual"].notna()
        & frame["plan"].notna()
        & feats["act_lag1"].notna()
        & feats["act_lag7"].notna()
        & feats["act_roll7"].notna()
    )
    return frame.loc[mask], names


def fold_windows(last_date: pd.Timestamp, folds: int, test_days: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    windows = []
    for k in range(folds):
        end = last_date - pd.Timedelta(days=(folds - 1 - k) * test_days)
        start = end - pd.Timedelta(days=test_days - 1)
        windows.append((start, end))
    return windows


def _mae(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean(np.abs(y - p)))


def _rmse(y: np.ndarray, p: np.ndarray) -> float:
    return float(math.sqrt(float(np.mean((y - p) ** 2))))


def block_bootstrap_difference(
    error_model: np.ndarray, error_base: np.ndarray, *, seed: int = RANDOM_STATE
) -> dict[str, float]:
    """95% moving-block bootstrap interval for mean(|e_model|) - mean(|e_base|).

    Negative values mean the model has smaller absolute errors.
    """
    diff = np.asarray(error_model, dtype=float) - np.asarray(error_base, dtype=float)
    n = len(diff)
    block = min(BOOTSTRAP_BLOCK_DAYS, n)
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n - block + 1, size=(BOOTSTRAP_RESAMPLES, math.ceil(n / block)))
    index = (starts[:, :, None] + np.arange(block)).reshape(BOOTSTRAP_RESAMPLES, -1)[:, :n]
    means = diff[index].mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return {"estimate": float(diff.mean()), "ci_low": float(low), "ci_high": float(high)}


def _window_sums(residuals: pd.Series, windows: list[tuple[pd.Timestamp, pd.Timestamp]], horizon: int) -> np.ndarray:
    """Every ``horizon``-day window inside the test folds, as an estimated total.

    A window is used when at least 70% of its days have a residual. The total is the mean of the
    available residuals multiplied by ``horizon``, so days without an actual do not bias it.
    """
    min_periods = max(1, math.ceil(0.7 * horizon))
    totals: list[np.ndarray] = []
    for start, end in windows:
        daily = residuals.reindex(pd.date_range(start, end, freq="D"))
        estimated = daily.rolling(horizon, min_periods=min_periods).mean() * horizon
        totals.append(estimated.dropna().to_numpy())
    return np.concatenate(totals) if totals else np.array([])


# ----------------------------------------------------------------------------
# Training and backtest
# ----------------------------------------------------------------------------
@dataclass
class TrainedForecaster:
    scope_key: str
    scope_label: str
    dataset_id: str
    fingerprint: str
    config: TrainingConfig
    feature_names: list[str]
    gradient_boosting: HistGradientBoostingRegressor
    ridge: Pipeline
    classifier: Pipeline
    oos: pd.DataFrame
    fold_table: list[dict[str, Any]]
    metrics: dict[str, Any]
    drivers: dict[str, Any]
    last_actual_date: str
    first_universe_date: str
    labelled_days: int
    trained_at: str
    versions: dict[str, str]


def train_forecaster(
    series: pd.DataFrame,
    *,
    scope: Scope,
    dataset_id: str,
    fingerprint: str,
    config: TrainingConfig,
    now: datetime | None = None,
) -> TrainedForecaster:
    universe, names = prepare_universe(series)
    if len(universe) < config.min_train_days + config.folds * config.test_days:
        needed = config.min_train_days + config.folds * config.test_days
        raise InsufficientDataError(
            f"Not enough complete days to backtest this scope: found {len(universe)}, "
            f"need at least {needed} (training {config.min_train_days} + {config.folds} test windows "
            f"of {config.test_days} days). Add more recorded actuals or choose a larger scope.",
            details={"complete_days": len(universe), "required_days": needed},
        )

    last_universe = pd.Timestamp(universe.index.max())
    windows = fold_windows(last_universe, config.folds, config.test_days)
    oos_parts: list[pd.DataFrame] = []
    fold_table: list[dict[str, Any]] = []
    last_fold_models: tuple[HistGradientBoostingRegressor, np.ndarray, np.ndarray] | None = None

    for fold_index, (start, end) in enumerate(windows, start=1):
        train = universe.loc[universe.index < start]
        test = universe.loc[(universe.index >= start) & (universe.index <= end)]
        if len(train) < config.min_train_days or test.empty:
            raise InsufficientDataError(
                f"Backtest fold {fold_index} has {len(train)} training days and {len(test)} test days; "
                f"at least {config.min_train_days} training days are required.",
                details={"fold": fold_index, "train_days": len(train), "test_days": len(test)},
            )
        x_train = train[names].to_numpy(dtype=float)
        y_train = train["actual"].to_numpy(dtype=float)
        s_train = train["short"].to_numpy(dtype=float)
        x_test = test[names].to_numpy(dtype=float)

        gbr = make_gradient_boosting().fit(x_train, y_train)
        ridge = make_ridge().fit(x_train, y_train)
        clf = make_shortfall_classifier().fit(x_train, s_train)
        climatology = float(np.mean(s_train))

        part = pd.DataFrame(
            {
                "date": test.index,
                "fold": fold_index,
                "actual": test["actual"].to_numpy(dtype=float),
                "plan": test["plan"].to_numpy(dtype=float),
                "short": test["short"].to_numpy(dtype=float),
                "pred_gradient_boosting": gbr.predict(x_test),
                "pred_ridge": ridge.predict(x_test),
                "base_plan": test["base_plan"].to_numpy(dtype=float),
                "base_persistence": test["base_persistence"].to_numpy(dtype=float),
                "base_seasonal_naive_7": test["base_seasonal_naive_7"].to_numpy(dtype=float),
                "base_moving_average_7": test["base_moving_average_7"].to_numpy(dtype=float),
                "p_short": clf.predict_proba(x_test)[:, 1],
                "p_climatology": climatology,
            }
        )
        oos_parts.append(part)
        fold_table.append(
            {
                "fold": fold_index,
                "train_end": (start - pd.Timedelta(days=1)).date().isoformat(),
                "test_start": start.date().isoformat(),
                "test_end": end.date().isoformat(),
                "train_days": len(train),
                "test_days": len(test),
                "gradient_boosting_mae": _mae(part["actual"].to_numpy(), part["pred_gradient_boosting"].to_numpy()),
            }
        )
        if fold_index == config.folds:
            last_fold_models = (gbr, x_test, part["actual"].to_numpy(dtype=float))

    oos = pd.concat(oos_parts).set_index("date").sort_index()
    metrics = _evaluate(oos, windows, config)
    drivers = _drivers(last_fold_models, names, universe, config)

    # Final models: fitted on every universe day, used for the forward forecast.
    x_all = universe[names].to_numpy(dtype=float)
    y_all = universe["actual"].to_numpy(dtype=float)
    s_all = universe["short"].to_numpy(dtype=float)
    final_gbr = make_gradient_boosting().fit(x_all, y_all)
    final_ridge = make_ridge().fit(x_all, y_all)
    final_clf = make_shortfall_classifier().fit(x_all, s_all)
    drivers["shortfall_coefficients"] = _coefficients(final_clf, names)

    return TrainedForecaster(
        scope_key=scope.key,
        scope_label=scope.label,
        dataset_id=dataset_id,
        fingerprint=fingerprint,
        config=config,
        feature_names=names,
        gradient_boosting=final_gbr,
        ridge=final_ridge,
        classifier=final_clf,
        oos=oos,
        fold_table=fold_table,
        metrics=metrics,
        drivers=drivers,
        last_actual_date=pd.Timestamp(series["actual"].last_valid_index()).date().isoformat(),
        first_universe_date=pd.Timestamp(universe.index.min()).date().isoformat(),
        labelled_days=len(universe),
        trained_at=(now or datetime.now(UTC)).isoformat(timespec="seconds"),
        versions={
            "scikit_learn": sklearn.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "model_version": MODEL_VERSION,
        },
    )


def _evaluate(
    oos: pd.DataFrame, windows: list[tuple[pd.Timestamp, pd.Timestamp]], config: TrainingConfig
) -> dict[str, Any]:
    y = oos["actual"].to_numpy(dtype=float)
    predictions: dict[str, np.ndarray] = {
        "gradient_boosting": oos["pred_gradient_boosting"].to_numpy(dtype=float),
        "ridge": oos["pred_ridge"].to_numpy(dtype=float),
        "plan": oos["base_plan"].to_numpy(dtype=float),
        "persistence": oos["base_persistence"].to_numpy(dtype=float),
        "seasonal_naive_7": oos["base_seasonal_naive_7"].to_numpy(dtype=float),
        "moving_average_7": oos["base_moving_average_7"].to_numpy(dtype=float),
    }
    errors = {name: np.abs(y - pred) for name, pred in predictions.items()}
    models: list[dict[str, Any]] = []
    for name, pred in predictions.items():
        models.append(
            {
                "name": name,
                "label": MODEL_LABELS.get(name, BASELINE_LABELS.get(name, name)),
                "kind": "model" if name in MODEL_KEYS else "baseline",
                "mae": round(_mae(y, pred), 2),
                "rmse": round(_rmse(y, pred), 2),
                "n": len(y),
            }
        )
    baseline_rows = [m for m in models if m["kind"] == "baseline"]
    best_baseline = min(baseline_rows, key=lambda m: m["mae"])
    best_errors = errors[best_baseline["name"]]
    per_fold: list[dict[str, Any]] = []
    for fold_index in sorted(oos["fold"].unique()):
        mask = (oos["fold"] == fold_index).to_numpy()
        row: dict[str, Any] = {"fold": int(fold_index), "n": int(mask.sum())}
        for name, pred in predictions.items():
            row[f"{name}_mae"] = round(_mae(y[mask], pred[mask]), 2)
        per_fold.append(row)
    mae_stats = {
        name: {
            "mean": round(float(np.mean([row[f"{name}_mae"] for row in per_fold])), 2),
            "std": round(float(np.std([row[f"{name}_mae"] for row in per_fold], ddof=0)), 2),
        }
        for name in predictions
    }
    comparison = block_bootstrap_difference(errors["gradient_boosting"], best_errors, seed=RANDOM_STATE)
    gb_mae = next(m["mae"] for m in models if m["name"] == "gradient_boosting")
    skill_pct = (1.0 - gb_mae / best_baseline["mae"]) * 100.0 if best_baseline["mae"] else None
    if comparison["ci_high"] < 0:
        verdict = "beats_best_baseline"
        verdict_text = (
            "The gradient boosting model has lower MAE than the best baseline, and the 95% interval for the "
            "difference excludes zero on this backtest."
        )
    elif comparison["ci_low"] > 0:
        verdict = "worse_than_best_baseline"
        verdict_text = (
            "The gradient boosting model has higher MAE than the best baseline, and the 95% interval excludes zero. "
            "Treat the ML forecast as provisional and rely on the baseline."
        )
    else:
        verdict = "no_reliable_difference"
        verdict_text = (
            "The difference from the best baseline is within the 95% uncertainty of this backtest. "
            "The model does not demonstrably beat a simple baseline."
        )
    ridge_mae = next(m["mae"] for m in models if m["name"] == "ridge")
    if ridge_mae < gb_mae:
        verdict_text += (
            f" A linear benchmark (ridge, MAE {ridge_mae:,.1f} t) had lower MAE than the gradient boosting model "
            f"(MAE {gb_mae:,.1f} t) on this backtest. The forecast keeps the gradient boosting model, which was "
            "chosen before the backtest was run."
        )

    residual = pd.Series(y - predictions["gradient_boosting"], index=oos.index)
    q10, q90 = np.percentile(residual.to_numpy(), [10, 90])

    classification = _classification_metrics(oos, windows)
    return {
        "method": (
            f"Expanding-window backtest: {config.folds} folds of {config.test_days} days, one-step-ahead, "
            "trained only on earlier days."
        ),
        "evaluation_start": oos.index.min().date().isoformat(),
        "evaluation_end": oos.index.max().date().isoformat(),
        "n_evaluated_days": len(y),
        "models": models,
        "per_fold": per_fold,
        "mae_by_fold": mae_stats,
        "best_baseline": best_baseline["name"],
        "gap_to_best_baseline": {
            "mae_difference": round(comparison["estimate"], 2),
            "ci95_low": round(comparison["ci_low"], 2),
            "ci95_high": round(comparison["ci_high"], 2),
            "skill_pct_vs_best_baseline": round(skill_pct, 2) if skill_pct is not None else None,
            "bootstrap": f"moving-block bootstrap, {BOOTSTRAP_RESAMPLES} resamples, {BOOTSTRAP_BLOCK_DAYS}-day blocks",
        },
        "verdict": verdict,
        "verdict_text": verdict_text,
        "residual_q10_t": round(float(q10), 2),
        "residual_q90_t": round(float(q90), 2),
        "classification": classification,
    }


def _classification_metrics(oos: pd.DataFrame, windows: list[tuple[pd.Timestamp, pd.Timestamp]]) -> dict[str, Any]:
    shortfall = oos["short"].to_numpy(dtype=float)
    p = oos["p_short"].to_numpy(dtype=float)
    clim = oos["p_climatology"].to_numpy(dtype=float)
    base_rate = float(shortfall.mean())
    brier = float(brier_score_loss(shortfall, p))
    brier_clim = float(np.mean((clim - shortfall) ** 2))
    auc: float | None = None
    if 0 < base_rate < 1:
        auc = float(roc_auc_score(shortfall, p))
    calibration: list[dict[str, Any]] = []
    if len(p) >= 50:
        bins = pd.qcut(pd.Series(p), q=5, duplicates="drop")
        frame = pd.DataFrame({"bin": bins.to_numpy(), "p": p, "y": shortfall})
        for label, group in frame.groupby("bin", observed=True):
            calibration.append(
                {
                    "bin": str(label),
                    "n": len(group),
                    "mean_predicted": round(float(group["p"].mean()), 3),
                    "observed_rate": round(float(group["y"].mean()), 3),
                }
            )
    return {
        "target": (
            f"Material shortfall day: actual below {100 - policy.SHORTFALL_DAY_TOLERANCE_PCT:g}% of planned tonnes."
        ),
        "model": "Logistic regression (standardised features, median imputation)",
        "n": len(shortfall),
        "base_rate": round(base_rate, 3),
        "roc_auc": round(auc, 3) if auc is not None else None,
        "brier": round(brier, 4),
        "brier_climatology": round(brier_clim, 4),
        "brier_skill_pct": round((1.0 - brier / brier_clim) * 100.0, 2) if brier_clim > 0 else None,
        "calibration": calibration,
    }


def _drivers(
    last_fold: tuple[HistGradientBoostingRegressor, np.ndarray, np.ndarray] | None,
    names: list[str],
    universe: pd.DataFrame,
    config: TrainingConfig,
) -> dict[str, Any]:
    if last_fold is None:
        return {"forecast_drivers": [], "method": "unavailable"}
    model, x_test, y_test = last_fold
    result = permutation_importance(
        model,
        x_test,
        y_test,
        n_repeats=10,
        random_state=RANDOM_STATE,
        scoring="neg_mean_absolute_error",
    )
    order = np.argsort(-result.importances_mean)
    items = [
        {
            "feature": names[i],
            "label": _feature_label(names[i]),
            "importance_t": round(float(result.importances_mean[i]), 3),
        }
        for i in order[:8]
    ]
    return {
        "forecast_drivers": items,
        "method": (
            "Permutation importance on the final backtest fold (held out from that fold's model): the increase "
            "in MAE when one feature is shuffled. Measures reliance, not causation."
        ),
    }


def _coefficients(clf: Pipeline, names: list[str]) -> list[dict[str, Any]]:
    coef = clf.named_steps["logisticregression"].coef_[0]
    order = np.argsort(-np.abs(coef))
    return [
        {
            "feature": names[i],
            "label": _feature_label(names[i]),
            "standardised_coefficient": round(float(coef[i]), 4),
            "direction": "raises shortfall probability" if coef[i] > 0 else "lowers shortfall probability",
        }
        for i in order[:8]
    ]


FEATURE_LABELS: dict[str, str] = {
    "plan": "Planned tonnes for the day",
    "act_lag1": "Actual, previous day",
    "act_lag2": "Actual, two days earlier",
    "act_lag7": "Actual, same weekday last week",
    "act_roll7": "Mean actual, last 7 days",
    "act_roll28": "Mean actual, last 28 days",
    "att_roll7": "Attainment, last 7 days",
    "downtime_lag1": "Equipment downtime, previous day",
    "downtime_roll7": "Equipment downtime, 7-day mean",
    "weather_lag1": "Weather delay, previous day",
    "weather_roll7": "Weather delay, 7-day mean",
    "blasting_lag1": "Blasting delay, previous day",
    "blasting_roll7": "Blasting delay, 7-day mean",
    "rain_lag1": "Rainfall, previous day",
    "rain_roll7": "Rainfall, 7-day mean",
    "dow_sin": "Day of week (sine)",
    "dow_cos": "Day of week (cosine)",
    "doy_sin": "Season (sine)",
    "doy_cos": "Season (cosine)",
}


def _feature_label(name: str) -> str:
    return FEATURE_LABELS.get(name, name)


# ----------------------------------------------------------------------------
# Forward forecast (recursive) and persistence
# ----------------------------------------------------------------------------
def forecast_forward(
    series: pd.DataFrame,
    model: TrainedForecaster,
    horizon: int,
) -> dict[str, Any]:
    """Recursive forecast for up to ``horizon`` days after the last recorded actual."""
    last_actual = pd.Timestamp(series["actual"].last_valid_index())
    future_days = pd.date_range(last_actual + pd.Timedelta(days=1), periods=horizon, freq="D")
    extended = series.reindex(series.index.union(future_days)).copy()
    extended.index.name = "date"

    scenario_window = series.loc[:last_actual].tail(SCENARIO_WINDOW_DAYS)
    scenario: dict[str, float] = {}
    for column in ("equipment_downtime_h", "weather_delay_h", "blasting_delay_h", "rainfall_mm"):
        if column in scenario_window.columns and scenario_window[column].notna().any():
            scenario[column] = float(scenario_window[column].mean())
            extended.loc[future_days, column] = scenario[column]

    rows: list[dict[str, Any]] = []
    truncated_at: str | None = None
    for day in future_days:
        if pd.isna(extended.at[day, "plan"]):
            truncated_at = day.date().isoformat()
            break
        feats = build_features(extended.loc[:day])
        x = feats.loc[[day], model.feature_names].to_numpy(dtype=float)
        pred = float(model.gradient_boosting.predict(x)[0])
        p_short = float(model.classifier.predict_proba(x)[0, 1])
        plan = float(extended.at[day, "plan"])
        rows.append(
            {
                "date": day.date().isoformat(),
                "plan_t": round(plan, 1),
                "forecast_t": round(pred, 1),
                "interval_low_t": round(pred + model.metrics["residual_q10_t"], 1),
                "interval_high_t": round(pred + model.metrics["residual_q90_t"], 1),
                "shortfall_probability": round(p_short, 3),
            }
        )
        extended.at[day, "actual"] = pred  # later days build on this day's forecast

    horizon_done = len(rows)
    result: dict[str, Any] = {
        "requested_days": horizon,
        "forecast_days": horizon_done,
        "truncated_reason": (
            f"No planned tonnage is recorded for {truncated_at}, so the horizon stops there." if truncated_at else None
        ),
        "scenario_assumptions": {
            "window_days": SCENARIO_WINDOW_DAYS,
            "values": {k: round(v, 2) for k, v in scenario.items()},
            "description": (
                "Operational inputs for future days are held at their trailing "
                f"{SCENARIO_WINDOW_DAYS}-day means. This is a scenario, not a prediction of delays."
            ),
        },
        "days": rows,
    }
    if horizon_done == 0:
        return result

    plan_total = float(sum(day["plan_t"] for day in rows))
    forecast_total = float(sum(day["forecast_t"] for day in rows))
    net = forecast_total - plan_total
    fold_windows_list = [(pd.Timestamp(row["test_start"]), pd.Timestamp(row["test_end"])) for row in model.fold_table]
    sums = _window_sums(model_residuals(model), fold_windows_list, horizon_done)
    gap_low: float | None = None
    gap_high: float | None = None
    prob_shortfall: float | None = None
    if len(sums) >= 20:
        s_low, s_high = np.percentile(sums, [10, 90])
        prob_shortfall = float(np.mean(sums < -net))
        gap_low, gap_high = net + float(s_low), net + float(s_high)
        interval_basis = (
            f"empirical 10th-90th percentile of {len(sums)} overlapping {horizon_done}-day backtest windows"
        )
    else:
        interval_basis = "not estimated: fewer than 20 complete backtest windows of this length"
    result["totals"] = {
        "plan_t": round(plan_total, 1),
        "forecast_t": round(forecast_total, 1),
        "net_gap_t": round(net, 1),
        "net_gap_pct": round(net / plan_total * 100.0, 2) if plan_total else None,
        "gap_interval_low_t": round(gap_low, 1) if gap_low is not None else None,
        "gap_interval_high_t": round(gap_high, 1) if gap_high is not None else None,
        "interval_basis": interval_basis,
        "period_shortfall_probability": round(prob_shortfall, 3) if prob_shortfall is not None else None,
        "mean_daily_shortfall_probability": round(float(np.mean([d["shortfall_probability"] for d in rows])), 3),
        "start": rows[0]["date"],
        "end": rows[-1]["date"],
    }
    return result


def model_residuals(model: TrainedForecaster) -> pd.Series:
    residual = model.oos["actual"] - model.oos["pred_gradient_boosting"]
    return residual.astype(float)


def save_forecaster(model: TrainedForecaster, artifacts_dir: Path) -> Path:
    target_dir = artifacts_dir / "models" / model.dataset_id
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{model.scope_key}.joblib"
    tmp = path.with_suffix(".joblib.tmp")
    joblib.dump(model, tmp)
    tmp.replace(path)
    return path


def load_forecaster(path: Path) -> TrainedForecaster | None:
    """Load a saved model. Returns None when the file is missing or was saved by another version."""
    if not path.exists():
        return None
    try:
        loaded = joblib.load(path)
    except Exception:
        return None
    if not isinstance(loaded, TrainedForecaster):
        return None
    if loaded.versions.get("scikit_learn") != sklearn.__version__:
        return None
    return loaded


def model_card(model: TrainedForecaster, source: str) -> dict[str, Any]:
    return {
        "name": "Gradient boosting regressor (scikit-learn HistGradientBoosting) with plan-based shortfall classifier",
        "regressor": MODEL_LABELS["gradient_boosting"],
        "classifier": "Logistic regression for P(actual < plan) on a day",
        "value_kind": "forecast",
        "source": source,
        "model_version": MODEL_VERSION,
        "fingerprint": model.fingerprint,
        "trained_at": model.trained_at,
        "trained_on": {
            "labelled_days": model.labelled_days,
            "first_day": model.first_universe_date,
            "last_actual_day": model.last_actual_date,
        },
        "features": model.feature_names,
        "config": model.config.as_dict(),
        "versions": model.versions,
        "random_state": RANDOM_STATE,
    }


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: as_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [as_json_safe(v) for v in value]
    return value
