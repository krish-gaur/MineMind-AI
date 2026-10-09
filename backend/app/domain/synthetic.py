"""Deterministic SYNTHETIC production generator (demonstration data only).

Nothing produced here is MOIL data. Mine and zone identifiers are fictional
(``SYN-*``), parameters are invented for illustration, and no calibration to any
real operation has been performed. The generator exists so that the workflow
(validation, KPIs, forecasting, risk, recommendations, reports) can be exercised
end-to-end with realistic *shapes*: monsoon-linked weather stoppages, lagged
downtime effects, a recurring breakdown pattern in one zone, blasting delays and
gaps in the record.

Reproducibility: the same ``GENERATOR_VERSION`` and ``SEED`` always produce a
byte-identical CSV (verified by tests through its SHA-256 fingerprint).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

GENERATOR_VERSION = "synthetic-production-v1.0"
DEMO_DATASET_ID = "demo-synthetic-production-v1"
SEED = 26009
HISTORY_START = date(2023, 4, 1)
HISTORY_END = date(2026, 9, 30)
PENDING_DAYS = 30  # plan-only days after HISTORY_END (no actuals yet)

# Fixed (illustrative) monthly plan profile: multipliers on the zone base plan.
MONTH_PLAN = {
    1: 1.00,
    2: 1.00,
    3: 1.08,
    4: 0.95,
    5: 1.00,
    6: 0.88,
    7: 0.84,
    8: 0.86,
    9: 0.92,
    10: 1.04,
    11: 1.10,
    12: 1.05,
}
MONSOON_MONTHS = frozenset({6, 7, 8, 9})

MINE_NAMES = {
    "SYN-A": "Synthetic Mine A",
    "SYN-B": "Synthetic Mine B",
    "SYN-C": "Synthetic Mine C",
}
MINE_RAIN_FACTOR = {"SYN-A": 1.00, "SYN-B": 0.90, "SYN-C": 1.10}

OUTPUT_COLUMNS = [
    "date",
    "mine_id",
    "zone_id",
    "planned_production_t",
    "actual_production_t",
    "equipment_downtime_h",
    "weather_delay_h",
    "blasting_delay_h",
    "rainfall_mm",
]


@dataclass(frozen=True)
class SeriesSpec:
    mine_id: str
    zone_id: str
    base_plan_tpd: float  # planned tonnes per day in an average month
    downtime_mean_h: float  # mean equipment downtime per day (hours)
    breakdown_rate: float  # probability per day that a multi-day breakdown episode starts
    blast_prob: float  # probability per day of a blasting delay event
    grade_sd: float  # sd of an unobserved productivity process (not in the dataset)


SERIES: tuple[SeriesSpec, ...] = (
    SeriesSpec("SYN-A", "SYN-A-Z1", 1450.0, 2.0, 0.004, 0.10, 0.020),
    SeriesSpec("SYN-A", "SYN-A-Z2", 900.0, 4.2, 0.030, 0.12, 0.030),
    SeriesSpec("SYN-B", "SYN-B-E", 1100.0, 2.4, 0.006, 0.26, 0.020),
    SeriesSpec("SYN-B", "SYN-B-W", 700.0, 1.8, 0.004, 0.10, 0.020),
    SeriesSpec("SYN-C", "SYN-C-C1", 500.0, 3.0, 0.008, 0.14, 0.030),
)


def _monsoon_mask(months: np.ndarray) -> np.ndarray:
    return np.isin(months, sorted(MONSOON_MONTHS))


def _regional_rain(rng: np.random.Generator, months: np.ndarray) -> np.ndarray:
    """Two-state Markov wet/dry chain with a seasonal monsoon regime (mm/day, shared region)."""
    n = len(months)
    wet = np.zeros(n, dtype=bool)
    monsoon = _monsoon_mask(months)
    draws = rng.random(n)
    for t in range(1, n):
        # Wet spells persist longer in the monsoon regime.
        p_wet = (0.75 if wet[t - 1] else 0.35) if monsoon[t] else (0.35 if wet[t - 1] else 0.05)
        wet[t] = draws[t] < p_wet
    scale = np.where(monsoon, 14.0, 7.0)
    amount = rng.gamma(shape=1.1, scale=scale)
    return np.where(wet, amount, 0.0)


def _mine_rain(rng: np.random.Generator, regional: np.ndarray, mine_id: str) -> np.ndarray:
    jitter = rng.lognormal(mean=0.0, sigma=0.15, size=len(regional))
    rain = regional * MINE_RAIN_FACTOR[mine_id] * jitter
    return np.round(np.where(regional > 0, rain, 0.0), 1)


def _downtime(rng: np.random.Generator, spec: SeriesSpec, monsoon: np.ndarray) -> np.ndarray:
    n = len(monsoon)
    mu = np.where(monsoon, spec.downtime_mean_h * 1.12, spec.downtime_mean_h)
    noise = rng.normal(0.0, 0.9, size=n)
    x = np.empty(n)
    x[0] = mu[0]
    for t in range(1, n):
        x[t] = mu[t] + 0.55 * (x[t - 1] - mu[t]) + noise[t]
    t = 0
    starts = rng.random(n) < spec.breakdown_rate
    while t < n:
        if starts[t]:
            length = int(rng.integers(3, 8))
            extra = float(rng.uniform(4.0, 9.0))
            x[t : t + length] += extra
            t += length
        else:
            t += 1
    return np.round(np.clip(x, 0.0, 24.0), 2)


def _blasting(rng: np.random.Generator, spec: SeriesSpec, dow: np.ndarray) -> np.ndarray:
    n = len(dow)
    # Tuesday and Friday are the scheduled blast days in this illustration.
    prob = spec.blast_prob * np.where(np.isin(dow, [1, 4]), 1.5, 0.8)
    events = rng.random(n) < prob
    duration = rng.uniform(2.0, 8.0, size=n)
    second = (rng.random(n) < 0.10) & events
    hours = np.where(events, duration, 0.0) + np.where(second, 3.0, 0.0)
    return np.round(np.clip(hours, 0.0, 24.0), 2)


def _weather_delay(rng: np.random.Generator, rain: np.ndarray) -> np.ndarray:
    base = np.where(rain >= 2.0, np.minimum(24.0, 1.1 * np.power(rain, 0.85)), 0.0)
    noise = rng.normal(0.0, 0.4, size=len(rain))
    occasional = (rng.random(len(rain)) < 0.02) * rng.uniform(0.5, 2.5, size=len(rain))
    return np.round(np.clip(base + noise + occasional, 0.0, 24.0), 2)


def generate_production_frame(seed: int = SEED) -> pd.DataFrame:
    """Return the synthetic production table (history plus pending plan rows)."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(HISTORY_START, pd.Timestamp(HISTORY_END) + pd.Timedelta(days=PENDING_DAYS), freq="D")
    n_hist = int((pd.Timestamp(HISTORY_END) - pd.Timestamp(HISTORY_START)).days) + 1
    months = dates.month.to_numpy()
    dow = dates.dayofweek.to_numpy()
    monsoon = _monsoon_mask(months)
    regional = _regional_rain(rng, months)
    n_total = len(dates)
    trend = np.linspace(0.0, 0.02, n_hist)

    frames: list[pd.DataFrame] = []
    rain_by_mine = {mine: _mine_rain(rng, regional, mine) for mine in MINE_NAMES}
    for spec in SERIES:
        rain = rain_by_mine[spec.mine_id]
        month_factor = np.array([MONTH_PLAN[int(m)] for m in months])
        plan = spec.base_plan_tpd * month_factor * np.where(dow == 6, 0.5, 1.0)
        plan = np.round(plan, 1)

        downtime = _downtime(rng, spec, monsoon)
        weather = _weather_delay(rng, rain)
        blasting = _blasting(rng, spec, dow)
        grade = np.zeros(n_total)
        innovation = rng.normal(0.0, spec.grade_sd * np.sqrt(1 - 0.92**2), size=n_total)
        for t in range(1, n_total):
            grade[t] = 0.92 * grade[t - 1] + innovation[t]

        lag_downtime = np.concatenate([[downtime[0]], downtime[:-1]])
        loss = 0.021 * downtime + 0.011 * weather + 0.017 * blasting + 0.006 * lag_downtime
        efficiency = (1.0 - loss) * (1.0 + grade) * (1.0 + rng.normal(0.0, 0.025, size=n_total))
        efficiency[:n_hist] *= 1.0 + trend
        actual = plan * np.clip(efficiency, 0.25, 1.10)

        # Recording problems: sensor/transcription outliers, missing actuals and missing hours.
        outlier = rng.random(n_total) < 0.004
        factor = rng.choice([1.6, 0.45], size=n_total)
        actual = np.where(outlier, actual * factor, actual)
        actual = np.round(actual, 1)
        missing_actual = rng.random(n_total) < 0.012
        actual = np.where(missing_actual, np.nan, actual)
        downtime = np.where(rng.random(n_total) < 0.004, np.nan, downtime)
        weather = np.where(rng.random(n_total) < 0.004, np.nan, weather)
        blasting = np.where(rng.random(n_total) < 0.004, np.nan, blasting)
        rain_out = np.where(rng.random(n_total) < 0.01, np.nan, rain)

        # Pending rows: plan exists, nothing recorded yet.
        actual[n_hist:] = np.nan
        downtime[n_hist:] = np.nan
        weather[n_hist:] = np.nan
        blasting[n_hist:] = np.nan
        rain_out[n_hist:] = np.nan

        frames.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "mine_id": spec.mine_id,
                    "zone_id": spec.zone_id,
                    "planned_production_t": plan,
                    "actual_production_t": actual,
                    "equipment_downtime_h": downtime,
                    "weather_delay_h": weather,
                    "blasting_delay_h": blasting,
                    "rainfall_mm": rain_out,
                }
            )
        )

    frame = pd.concat(frames, ignore_index=True)
    frame = frame[OUTPUT_COLUMNS].sort_values(["date", "mine_id", "zone_id"]).reset_index(drop=True)
    return frame


def frame_to_csv_bytes(frame: pd.DataFrame) -> bytes:
    """Serialise deterministically (fixed float format, ISO dates, blanks for missing)."""
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    text = out.to_csv(index=False, float_format="%.2f", na_rep="", lineterminator="\n")
    return text.encode("utf-8")


def generator_metadata(seed: int = SEED) -> dict[str, Any]:
    return {
        "generator": GENERATOR_VERSION,
        "seed": seed,
        "history_start": HISTORY_START.isoformat(),
        "history_end": HISTORY_END.isoformat(),
        "pending_days": PENDING_DAYS,
        "mines": {mine: MINE_NAMES[mine] for mine in MINE_NAMES},
        "zones": [spec.zone_id for spec in SERIES],
        "calibration": "None. Parameters are illustrative and not calibrated to any MOIL operation.",
    }
