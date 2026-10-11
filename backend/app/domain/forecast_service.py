"""Load-or-train orchestration and payload assembly for forecasts and risk.

A trained model is reused only when its data fingerprint and configuration still match.
Otherwise it is retrained and overwritten. Training is serialised with a lock so concurrent
requests for the same scope do not train twice.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.domain import policy
from app.domain.features import Scope, daily_series
from app.domain.forecasting import (
    MODEL_LABELS,
    TrainedForecaster,
    TrainingConfig,
    as_json_safe,
    forecast_forward,
    load_forecaster,
    model_card,
    model_residuals,
    save_forecaster,
    scope_fingerprint,
    train_forecaster,
)
from app.domain.provenance import SOURCE_LABELS, SourceType
from app.domain.risk import classification_verdict, classify_band
from app.domain.store import DatasetStore

MEMORY_LIMIT = 16
HISTORY_DAYS = 270


class ForecastService:
    def __init__(self, store: DatasetStore, artifacts_dir: Path, *, horizon_days: int) -> None:
        self._store = store
        self._artifacts_dir = Path(artifacts_dir)
        self._config = TrainingConfig(horizon_days=horizon_days)
        self._lock = threading.Lock()
        self._memory: OrderedDict[str, tuple[TrainedForecaster, pd.DataFrame]] = OrderedDict()

    @property
    def config(self) -> TrainingConfig:
        return self._config

    def model_for(self, dataset_id: str, scope: Scope) -> tuple[TrainedForecaster, pd.DataFrame, str]:
        """Return (model, daily series, source) where source is 'memory', 'loaded' or 'trained'."""
        frame = self._store.load_production(dataset_id)
        fingerprint = scope_fingerprint(frame, scope, self._config)
        memory_key = f"{dataset_id}|{scope.key}|{fingerprint}"
        with self._lock:
            cached = self._memory.get(memory_key)
            if cached is not None:
                self._memory.move_to_end(memory_key)
                return cached[0], cached[1], "memory"

            series = daily_series(frame, scope)
            path = self._artifacts_dir / "models" / dataset_id / f"{scope.key}.joblib"
            loaded = load_forecaster(path)
            if loaded is not None and loaded.fingerprint == fingerprint and loaded.config == self._config:
                model, source = loaded, "loaded"
            else:
                model = train_forecaster(
                    series,
                    scope=scope,
                    dataset_id=dataset_id,
                    fingerprint=fingerprint,
                    config=self._config,
                    now=datetime.now(UTC),
                )
                save_forecaster(model, self._artifacts_dir)
                source = "trained"

            self._memory[memory_key] = (model, series)
            while len(self._memory) > MEMORY_LIMIT:
                self._memory.popitem(last=False)
            return model, series, source

    # ------------------------------------------------------------------
    # Payloads
    # ------------------------------------------------------------------
    def forecast_payload(self, dataset_id: str, scope: Scope, horizon: int, dataset: dict[str, Any]) -> dict[str, Any]:
        model, series, source = self.model_for(dataset_id, scope)
        forward = forecast_forward(series, model, horizon)
        return as_json_safe(
            {
                "dataset": dataset,
                "scope": _scope_payload(scope),
                "model": model_card(model, source),
                "evaluation": _evaluation_payload(model),
                "classification": _classification_payload(model),
                "backtest_history": _history(model, series),
                "forecast": forward,
                "drivers": {
                    "forecast_drivers": model.drivers.get("forecast_drivers", []),
                    "forecast_drivers_method": model.drivers.get("method"),
                    "shortfall_coefficients": model.drivers.get("shortfall_coefficients", []),
                    "shortfall_method": (
                        "Standardised coefficients of the logistic shortfall model on all labelled days. "
                        "Describe associations in this dataset, not causes."
                    ),
                },
                "value_kinds": {
                    "forecast_t": "forecast",
                    "gap_t": "estimate",
                    "shortfall_probability": "probability",
                    "scenario_inputs": "scenario",
                },
                "notes": _forecast_notes(model, forward),
            }
        )

    def risk_payload(self, dataset_id: str, scope: Scope, horizon: int, dataset: dict[str, Any]) -> dict[str, Any]:
        model, series, source = self.model_for(dataset_id, scope)
        forward = forecast_forward(series, model, horizon)
        totals = forward.get("totals")
        if not totals:
            band = classify_band(None)
            return as_json_safe(
                {
                    "dataset": dataset,
                    "scope": _scope_payload(scope),
                    "horizon": {"requested_days": horizon, "forecast_days": 0, "start": None, "end": None},
                    "expected": None,
                    "shortfall_probability": None,
                    "band": band,
                    "classification_check": None,
                    "model_check": None,
                    "drivers": [],
                    "limitations": ["No forecast horizon could be produced because planned tonnage is missing."],
                    "source": source,
                }
            )
        classification = model.metrics["classification"]
        verdict_code, verdict_text = classification_verdict(classification)
        band = classify_band(totals["net_gap_pct"])
        return as_json_safe(
            {
                "dataset": dataset,
                "scope": _scope_payload(scope),
                "horizon": {
                    "requested_days": horizon,
                    "forecast_days": forward["forecast_days"],
                    "start": totals["start"],
                    "end": totals["end"],
                },
                "expected": {
                    "plan_t": totals["plan_t"],
                    "forecast_t": totals["forecast_t"],
                    "net_gap_t": totals["net_gap_t"],
                    "net_gap_pct": totals["net_gap_pct"],
                    "gap_interval_low_t": totals["gap_interval_low_t"],
                    "gap_interval_high_t": totals["gap_interval_high_t"],
                    "interval_basis": totals["interval_basis"],
                    "value_kind": "estimate",
                    "forecast_value_kind": "forecast",
                },
                "shortfall_probability": {
                    "period_probability": totals["period_shortfall_probability"],
                    "period_basis": (
                        "Share of backtest windows of the same length in which the realised gap was below plan, "
                        "given the forecast net gap. Empirical, not a calibrated model output."
                    ),
                    "mean_daily_probability": totals["mean_daily_shortfall_probability"],
                    "daily_definition": classification["target"],
                    "value_kind": "probability",
                },
                "band": band,
                "model_check": {
                    "regression_verdict": model.metrics["verdict"],
                    "regression_text": model.metrics["verdict_text"],
                    "classifier_verdict": verdict_code,
                },
                "classification_check": {
                    "verdict": verdict_code,
                    "text": verdict_text,
                    "roc_auc": classification["roc_auc"],
                    "brier_skill_pct": classification["brier_skill_pct"],
                    "base_rate": classification["base_rate"],
                    "n": classification["n"],
                },
                "drivers": model.drivers.get("forecast_drivers", []),
                "limitations": _risk_limitations(model, forward),
                "source": source,
            }
        )


def _scope_payload(scope: Scope) -> dict[str, Any]:
    return {"mine_id": scope.mine_id, "zone_id": scope.zone_id, "label": scope.label, "key": scope.key}


def _evaluation_payload(model: TrainedForecaster) -> dict[str, Any]:
    metrics = model.metrics
    return {
        "method": metrics["method"],
        "evaluation_start": metrics["evaluation_start"],
        "evaluation_end": metrics["evaluation_end"],
        "n_evaluated_days": metrics["n_evaluated_days"],
        "folds": model.fold_table,
        "models": metrics["models"],
        "per_fold": metrics["per_fold"],
        "mae_by_fold": metrics["mae_by_fold"],
        "best_baseline": metrics["best_baseline"],
        "gap_to_best_baseline": metrics["gap_to_best_baseline"],
        "verdict": metrics["verdict"],
        "verdict_text": metrics["verdict_text"],
        "residual_q10_t": metrics["residual_q10_t"],
        "residual_q90_t": metrics["residual_q90_t"],
        "model_labels": MODEL_LABELS,
    }


def _classification_payload(model: TrainedForecaster) -> dict[str, Any]:
    classification = dict(model.metrics["classification"])
    verdict_code, verdict_text = classification_verdict(classification)
    classification["verdict"] = verdict_code
    classification["verdict_text"] = verdict_text
    classification["value_kind"] = "probability"
    return classification


def _history(model: TrainedForecaster, series: pd.DataFrame) -> list[dict[str, Any]]:
    oos = model.oos.tail(HISTORY_DAYS)
    rows: list[dict[str, Any]] = []
    for day, row in oos.iterrows():
        rows.append(
            {
                "date": pd.Timestamp(day).date().isoformat(),
                "actual_t": _round(row["actual"]),
                "plan_t": _round(row["plan"]),
                "gradient_boosting_t": _round(row["pred_gradient_boosting"]),
                "ridge_t": _round(row["pred_ridge"]),
                "seasonal_naive_7_t": _round(row["base_seasonal_naive_7"]),
                "shortfall_probability": _round(row["p_short"], 3),
            }
        )
    del series
    return rows


def _round(value: Any, digits: int = 1) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return round(number, digits)


def _forecast_notes(model: TrainedForecaster, forward: dict[str, Any]) -> list[str]:
    notes = [
        "Forecast values are model outputs. They are not measurements and are not guaranteed.",
        "Backtest figures are out-of-sample for the periods shown; they say nothing about other periods.",
    ]
    if forward.get("truncated_reason"):
        notes.append(forward["truncated_reason"])
    if model.metrics["verdict"] != "beats_best_baseline":
        notes.append(
            "The ML forecast does not demonstrably beat the best simple baseline on this backtest. "
            "Use the baseline comparison when planning."
        )
    return notes


def _risk_limitations(model: TrainedForecaster, forward: dict[str, Any]) -> list[str]:
    items = [
        "Net gap is forecast plan minus forecast output over the horizon. Negative means shortfall.",
        "Interval and period probability are empirical from backtest residuals, "
        "not a calibrated predictive distribution.",
        "Future operational inputs (downtime, weather, blasting, rainfall) are scenario assumptions, "
        "so the forecast is conditional on them.",
        f"Band thresholds are policy: HIGH at or below -{policy.RISK_HIGH_SHORTFALL_PCT:g}%, "
        f"MEDIUM at or below -{policy.RISK_MEDIUM_SHORTFALL_PCT:g}%.",
        "The dataset contains no geology, grade or fleet-availability records, so these cannot explain shortfalls.",
    ]
    if model.metrics["verdict"] != "beats_best_baseline":
        items.append(
            "The forecast does not demonstrably beat the best baseline; band reliability is limited accordingly."
        )
    if forward.get("scenario_assumptions", {}).get("values"):
        items.append(
            "Scenario inputs use trailing means: "
            + ", ".join(f"{k} {v:g}" for k, v in forward["scenario_assumptions"]["values"].items())
            + "."
        )
    return items


def dataset_context(manifest: Any) -> dict[str, Any]:
    source_type = SourceType(manifest.source_type)
    return {
        "id": manifest.id,
        "name": manifest.name,
        "source_type": source_type.value,
        "source_label": SOURCE_LABELS[source_type],
        "is_synthetic": source_type is SourceType.SYNTHETIC,
        "banner": (
            "SYNTHETIC DEMONSTRATION DATA - not MOIL operational records. Forecasts and risk bands illustrate the "
            "workflow only."
            if source_type is SourceType.SYNTHETIC
            else None
        ),
        "date_max": manifest.date_max.isoformat() if isinstance(manifest.date_max, date) else None,
        "provenance": manifest.provenance.model_dump(mode="json"),
    }


__all__ = ["ForecastService", "dataset_context", "model_residuals"]
