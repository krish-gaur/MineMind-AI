"""Validation of production CSV uploads (``production.v1``).

Policy
------
* **Errors** block the upload. Row-level problems cite the file line so the
  user can fix the source file. Nothing is stored when errors exist.
* **Warnings** are accepted and reported. Rows without an actual value are kept
  as *pending*; they are never filled with invented numbers.
* **Outliers** are flagged with an IQR rule within each mine/zone series and
  left unchanged for review.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from app.domain.schema import (
    ID_PATTERN,
    NUMERIC_COLUMNS,
    OPERATIONAL_COLUMNS,
    PRODUCTION_COLUMNS,
    PRODUCTION_SCHEMA_VERSION,
    REQUIRED_COLUMNS,
    ColumnSpec,
)
from app.schemas.common import ColumnProfile, ValidationIssue, ValidationReport

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ID_RE = re.compile(ID_PATTERN)
MAX_EXAMPLES = 5
MAX_ROW_ERRORS = 50
IQR_FACTOR = 3.0
IQR_MIN_VALUES = 8
RAINFALL_UNUSUAL_MM = 500.0
NULL_TOKENS = frozenset({"", "NA", "N/A", "null", "NULL", "NaN", "nan", "-"})
KNOWN_COLUMNS = frozenset(spec.name for spec in PRODUCTION_COLUMNS)
COLUMN_SPECS: dict[str, ColumnSpec] = {spec.name: spec for spec in PRODUCTION_COLUMNS}


class ProductionFileError(Exception):
    """The file cannot be read as a production table at all (not a row-level problem)."""


@dataclass
class ValidationOutcome:
    report: ValidationReport
    frame: pd.DataFrame | None  # normalised, typed table when accepted; otherwise None


@dataclass
class _Collector:
    issues: list[ValidationIssue] = field(default_factory=list)

    def add(
        self,
        severity: str,
        code: str,
        message: str,
        *,
        affected: int = 0,
        examples: Sequence[str] = (),
    ) -> None:
        self.issues.append(
            ValidationIssue(
                severity=severity,  # type: ignore[arg-type]
                code=code,
                message=message,
                affected_rows=affected,
                examples=list(examples)[:MAX_EXAMPLES],
            )
        )

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)


def normalise_header(name: object) -> str:
    """Lower-case and map spaces/hyphens to underscores. Units must be spelled out in the name."""
    text = str(name).replace("\ufeff", "").strip().lower()
    return re.sub(r"[\s\-]+", "_", text)


def _decode(raw: bytes) -> str:
    if not raw or not raw.strip():
        raise ProductionFileError("The file is empty. Upload a CSV with a header row and data rows.")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ProductionFileError(
            "The file is not UTF-8 encoded. Save it as 'CSV UTF-8' and upload again."
        ) from exc


def _read_rows(text: str) -> tuple[list[str], list[tuple[int, list[str]]]]:
    """Return (header, [(file_line, cells), ...]) skipping completely blank lines."""
    reader = csv.reader(io.StringIO(text, newline=""), skipinitialspace=True)
    header: list[str] | None = None
    rows: list[tuple[int, list[str]]] = []
    try:
        for cells in reader:
            line = reader.line_num
            if not any(cell.strip() for cell in cells):
                continue
            if header is None:
                header = [normalise_header(cell) for cell in cells]
            else:
                rows.append((line, [cell.strip() for cell in cells]))
    except csv.Error as exc:
        raise ProductionFileError(f"The CSV could not be parsed near line {reader.line_num}: {exc}.") from exc
    if header is None:
        raise ProductionFileError("The file has no header row.")
    duplicated = sorted({name for name in header if name and header.count(name) > 1})
    if duplicated:
        raise ProductionFileError("Duplicate column names in the header: " + ", ".join(duplicated) + ".")
    return header, rows


def _check_header(header: list[str], collector: _Collector) -> None:
    missing = [name for name in REQUIRED_COLUMNS if name not in header]
    if missing:
        collector.add(
            "error",
            "missing_columns",
            "Required column(s) missing: "
            + ", ".join(missing)
            + ". Found: "
            + (", ".join(header) or "none")
            + ".",
        )
    unknown = [name for name in header if name not in KNOWN_COLUMNS]
    if unknown:
        collector.add(
            "warning",
            "unknown_columns",
            "Columns not used by MineMind AI were ignored: " + ", ".join(unknown) + ".",
            affected=len(unknown),
        )


def _typed_frame(
    header: list[str], rows: list[tuple[int, list[str]]], collector: _Collector
) -> pd.DataFrame | None:
    """Build a typed frame. Records row-level errors and returns None if any exist."""
    width = len(header)
    problems: dict[int, list[str]] = {}

    def problem(index: int, text: str) -> None:
        problems.setdefault(index, []).append(text)

    for index, (_line, cells) in enumerate(rows):
        if len(cells) != width:
            problem(index, f"expected {width} columns but found {len(cells)}")
    if problems:
        _report_rows(collector, rows, problems)
        return None

    table = pd.DataFrame([cells for _, cells in rows], columns=header, dtype=object).astype("string")
    table = table.fillna("")
    out: dict[str, pd.Series] = {}

    # --- dates -----------------------------------------------------------------
    raw_dates = table["date"].str.strip() if "date" in table else pd.Series("", index=table.index)
    date_format_ok = raw_dates.str.match(DATE_PATTERN).fillna(False).astype(bool)
    parsed = pd.to_datetime(raw_dates.where(date_format_ok), format="%Y-%m-%d", errors="coerce")
    bad_dates = (~date_format_ok) | parsed.isna()
    for i in np.flatnonzero(bad_dates.to_numpy()):
        problem(int(i), f"date '{raw_dates.iat[int(i)]}' is not a valid YYYY-MM-DD calendar date")
    out["date"] = parsed

    # --- identifiers -----------------------------------------------------------
    for column in ("mine_id", "zone_id"):
        values = table[column].str.strip()
        blank = values.eq("").to_numpy()
        invalid = (~values.str.match(ID_RE).fillna(False).astype(bool)).to_numpy() & ~blank
        for i in np.flatnonzero(blank):
            problem(int(i), f"{column} is blank")
        for i in np.flatnonzero(invalid):
            problem(int(i), f"{column} '{values.iat[int(i)]}' has invalid characters or is too long")
        out[column] = values.where(~(blank | invalid), "").astype(object)

    # --- numbers ---------------------------------------------------------------
    for column in NUMERIC_COLUMNS:
        if column not in table:
            out[column] = pd.Series(np.nan, index=table.index, dtype="float64")
            continue
        text = table[column].str.strip()
        blank = text.isin(NULL_TOKENS).to_numpy()
        kept = text.where(~pd.Series(blank, index=text.index)).astype(object)
        numbers = pd.to_numeric(kept, errors="coerce").astype("float64")
        invalid = (~blank) & numbers.isna().to_numpy()
        for i in np.flatnonzero(invalid):
            problem(int(i), f"{column} '{text.iat[int(i)]}' is not a number")
        if column == "planned_production_t":
            for i in np.flatnonzero(blank):
                problem(int(i), "planned_production_t is required but blank")
        spec = COLUMN_SPECS[column]
        valid = numbers.notna().to_numpy()
        if spec.min_value is not None:
            for i in np.flatnonzero(valid & (numbers.to_numpy() < spec.min_value)):
                problem(int(i), f"{column} must be >= {spec.min_value:g}")
        if spec.max_value is not None and column in OPERATIONAL_COLUMNS:
            for i in np.flatnonzero(valid & (numbers.to_numpy() > spec.max_value)):
                problem(int(i), f"{column} must be <= {spec.max_value:g}")
        out[column] = numbers.where(~pd.Series(invalid, index=numbers.index))

    if problems:
        _report_rows(collector, rows, problems)
        return None
    frame = pd.DataFrame(out, index=table.index)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def _report_rows(
    collector: _Collector, rows: list[tuple[int, list[str]]], problems: dict[int, list[str]]
) -> None:
    examples = [f"line {rows[index][0]}: " + "; ".join(texts) for index, texts in sorted(problems.items())]
    collector.add(
        "error",
        "row_errors",
        f"{len(problems)} row(s) contain problems. Fix them in the source file and upload again.",
        affected=len(problems),
        examples=examples[:MAX_ROW_ERRORS],
    )


def _check_duplicates(frame: pd.DataFrame, collector: _Collector) -> None:
    duplicate = frame.duplicated(["date", "mine_id", "zone_id"], keep=False)
    if not duplicate.any():
        return
    keys = frame.loc[duplicate, ["date", "mine_id", "zone_id"]].drop_duplicates()
    examples = [f"{d.date()} {m}/{z}" for d, m, z in keys.itertuples(index=False)]
    collector.add(
        "error",
        "duplicate_rows",
        "Each date / mine_id / zone_id combination must appear only once.",
        affected=int(duplicate.sum()),
        examples=examples,
    )


def _iqr_flags(frame: pd.DataFrame, column: str) -> pd.Series:
    flags = pd.Series(False, index=frame.index)
    for _, group in frame.groupby(["mine_id", "zone_id"], sort=False):
        values = group[column].dropna()
        if len(values) < IQR_MIN_VALUES:
            continue
        q1, q3 = float(values.quantile(0.25)), float(values.quantile(0.75))
        iqr = q3 - q1
        if iqr <= 0:
            continue
        low, high = q1 - IQR_FACTOR * iqr, q3 + IQR_FACTOR * iqr
        flags.loc[group.index] = ((group[column] < low) | (group[column] > high)).fillna(False)
    return flags


def _gap_days(frame: pd.DataFrame) -> int:
    gaps = 0
    for _, group in frame.groupby(["mine_id", "zone_id"], sort=False):
        days = group["date"].drop_duplicates().sort_values()
        if len(days) > 1:
            gaps += int((days.iloc[-1] - days.iloc[0]).days + 1 - len(days))
    return gaps


def _add_warnings(frame: pd.DataFrame, collector: _Collector, now: datetime) -> None:
    pending = frame["actual_production_t"].isna()
    if pending.any():
        collector.add(
            "warning",
            "pending_actuals",
            "Rows without an actual production value are treated as pending. They are excluded from "
            "actual-based KPIs and model training. No values were imputed.",
            affected=int(pending.sum()),
        )

    today = pd.Timestamp(now.date())
    future = frame["actual_production_t"].notna() & (frame["date"] > today)
    if future.any():
        collector.add(
            "warning",
            "future_actuals",
            "Actual values are dated after today's date. Check the date column.",
            affected=int(future.sum()),
        )

    gaps = _gap_days(frame)
    if gaps:
        collector.add(
            "warning",
            "date_gaps",
            f"{gaps} calendar day(s) are missing inside the recorded series. They are not filled.",
            affected=gaps,
        )

    comparable = frame["actual_production_t"].notna() & (frame["planned_production_t"] > 0)
    implausible = comparable & (frame["actual_production_t"] > 2.5 * frame["planned_production_t"])
    if implausible.any():
        collector.add(
            "warning",
            "actual_far_above_plan",
            "Actual output exceeds 2.5 times the plan on some rows. Verify these records.",
            affected=int(implausible.sum()),
            examples=[
                f"{frame.at[i, 'date'].date()} {frame.at[i, 'zone_id']}"
                for i in frame.index[implausible.to_numpy()]
            ],
        )

    if "rainfall_mm" in frame:
        extreme = frame["rainfall_mm"] > RAINFALL_UNUSUAL_MM
        if extreme.any():
            collector.add(
                "warning",
                "unusual_rainfall",
                f"Daily rainfall above {RAINFALL_UNUSUAL_MM:g} mm was recorded. Verify the station data.",
                affected=int(extreme.sum()),
            )

    for column in ("planned_production_t", "actual_production_t"):
        count = int(_iqr_flags(frame, column).sum())
        if count:
            collector.add(
                "warning",
                "outliers",
                f"{count} potential outlier(s) in {column} (IQR x{IQR_FACTOR:g} within each zone). "
                "Flagged for review; values were not changed.",
                affected=count,
            )


def _profile(frame: pd.DataFrame | None, spec: ColumnSpec, present: bool) -> ColumnProfile:
    base = ColumnProfile(name=spec.name, present=present, required=spec.required, unit=spec.unit)
    if not present or frame is None or spec.name not in frame:
        return base
    series = frame[spec.name]
    total = len(series)
    missing = int(series.isna().sum())
    base.missing_count = missing
    base.missing_pct = round(100.0 * missing / total, 2) if total else None
    if spec.name in NUMERIC_COLUMNS and series.notna().any():
        base.min = round(float(series.min()), 3)
        base.max = round(float(series.max()), 3)
        base.mean = round(float(series.mean()), 3)
    if spec.name in ("planned_production_t", "actual_production_t") and series.notna().any():
        base.outlier_count = int(_iqr_flags(frame, spec.name).sum())
        base.outlier_rule = f"IQR x{IQR_FACTOR:g} within each mine/zone series"
    return base


def _summary(frame: pd.DataFrame) -> dict[str, object]:
    actual = frame["actual_production_t"].notna()
    return {
        "date_min": frame["date"].min().date(),
        "date_max": frame["date"].max().date(),
        "series_count": int(frame.groupby(["mine_id", "zone_id"]).ngroups),
        "mines": sorted(frame["mine_id"].unique().tolist()),
        "zones": sorted(frame["zone_id"].unique().tolist()),
        "rows_with_actual": int(actual.sum()),
        "rows_pending_actual": int((~actual).sum()),
        "missing_date_gaps": _gap_days(frame),
    }


def _finish(
    collector: _Collector,
    row_count: int,
    header: list[str],
    frame: pd.DataFrame | None,
    now: datetime,
) -> ValidationOutcome:
    if collector.has_errors:
        status = "invalid"
    elif collector.issues:
        status = "valid_with_warnings"
    else:
        status = "valid"

    columns = [_profile(frame, spec, spec.name in header) for spec in PRODUCTION_COLUMNS]
    report_kwargs: dict[str, object] = {
        "status": status,
        "schema_version": PRODUCTION_SCHEMA_VERSION,
        "row_count": row_count,
        "issues": collector.issues,
        "columns": columns,
        "unknown_columns": [name for name in header if name not in KNOWN_COLUMNS],
        "generated_at": now,
    }
    accepted = frame if (status != "invalid" and frame is not None) else None
    if accepted is not None:
        report_kwargs.update(_summary(accepted))
    return ValidationOutcome(report=ValidationReport(**report_kwargs), frame=accepted)  # type: ignore[arg-type]


def validate_production_csv(raw: bytes, *, max_rows: int, now: datetime | None = None) -> ValidationOutcome:
    """Validate a production CSV.

    Content problems never raise; they are returned in the report. Only files that
    cannot be read at all (empty, not UTF-8, no header, duplicate headers) raise
    :class:`ProductionFileError`.
    """
    now = now or datetime.now(UTC)
    text = _decode(raw)
    header, rows = _read_rows(text)
    collector = _Collector()
    _check_header(header, collector)

    if any(name not in header for name in REQUIRED_COLUMNS):
        return _finish(collector, len(rows), header, None, now)
    if not rows:
        collector.add("error", "no_rows", "The file has a header but no data rows.")
        return _finish(collector, 0, header, None, now)
    if len(rows) > max_rows:
        collector.add(
            "error",
            "too_many_rows",
            f"The file has {len(rows):,} rows; the limit is {max_rows:,}. Split the file by period.",
            affected=len(rows),
        )
        return _finish(collector, len(rows), header, None, now)

    typed = _typed_frame(header, rows, collector)
    if typed is None:
        return _finish(collector, len(rows), header, None, now)

    _check_duplicates(typed, collector)
    if collector.has_errors:
        return _finish(collector, len(rows), header, None, now)

    frame = typed.sort_values(["date", "mine_id", "zone_id"]).reset_index(drop=True)
    _add_warnings(frame, collector, now)
    return _finish(collector, len(rows), header, frame, now)
