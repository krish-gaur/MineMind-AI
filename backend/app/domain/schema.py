"""Data contracts for uploaded and generated datasets.

``production.v1`` is the daily mine-zone production table. Column names are
canonical snake_case; uploads are matched case-insensitively with spaces or
hyphens converted to underscores (so "Planned Production (t)" must be renamed
to ``planned_production_t`` by the user - we only normalise case and separators).
"""

from __future__ import annotations

from dataclasses import dataclass

PRODUCTION_SCHEMA_VERSION = "production.v1"


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    dtype: str  # "date" | "id" | "number"
    required: bool
    unit: str
    description: str
    min_value: float | None = None
    max_value: float | None = None


PRODUCTION_COLUMNS: tuple[ColumnSpec, ...] = (
    ColumnSpec("date", "date", True, "YYYY-MM-DD", "Calendar day of the record."),
    ColumnSpec("mine_id", "id", True, "text", "Mine identifier (letters, digits, - _ .)."),
    ColumnSpec("zone_id", "id", True, "text", "Production zone / pit identifier within the mine."),
    ColumnSpec(
        "planned_production_t",
        "number",
        True,
        "tonnes",
        "Planned output for the zone on this day. Required for every row.",
        min_value=0,
    ),
    ColumnSpec(
        "actual_production_t",
        "number",
        True,
        "tonnes",
        "Measured output. May be blank for planned-but-not-yet-recorded days; blanks are never imputed.",
        min_value=0,
    ),
    ColumnSpec(
        "equipment_downtime_h",
        "number",
        False,
        "hours",
        "Hours lost to equipment failure or maintenance on this day.",
        min_value=0,
        max_value=24,
    ),
    ColumnSpec(
        "weather_delay_h",
        "number",
        False,
        "hours",
        "Hours lost to rain or other weather stoppages.",
        min_value=0,
        max_value=24,
    ),
    ColumnSpec(
        "blasting_delay_h",
        "number",
        False,
        "hours",
        "Hours lost to blasting delays (re-blasting, scheduling, clearance).",
        min_value=0,
        max_value=24,
    ),
    ColumnSpec(
        "rainfall_mm",
        "number",
        False,
        "mm/day",
        "Daily rainfall at the site (measured, or public reanalysis if enriched).",
        min_value=0,
        max_value=1500,
    ),
)

REQUIRED_COLUMNS: tuple[str, ...] = tuple(c.name for c in PRODUCTION_COLUMNS if c.required)
OPTIONAL_COLUMNS: tuple[str, ...] = tuple(c.name for c in PRODUCTION_COLUMNS if not c.required)
OPERATIONAL_COLUMNS: tuple[str, ...] = (
    "equipment_downtime_h",
    "weather_delay_h",
    "blasting_delay_h",
    "rainfall_mm",
)
NUMERIC_COLUMNS: tuple[str, ...] = (
    "planned_production_t",
    "actual_production_t",
    *OPERATIONAL_COLUMNS,
)
ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,39}$"
