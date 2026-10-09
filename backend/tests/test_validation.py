"""Dataset validation: schema checks, row-level errors, missing values and outliers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.validation import ProductionFileError, validate_production_csv
from tests.conftest import HEADER, csv_text

NOW = datetime(2026, 10, 9, tzinfo=UTC)
MAX_ROWS = 1000


def _validate(raw: bytes):  # type: ignore[no-untyped-def]
    return validate_production_csv(raw, max_rows=MAX_ROWS, now=NOW)


def _codes(outcome) -> set[str]:  # type: ignore[no-untyped-def]
    return {issue.code for issue in outcome.report.issues}


def test_valid_file_is_accepted_and_summarised() -> None:
    outcome = _validate(
        csv_text(
            "2026-09-01,SYN-A,SYN-A-Z1,1000,950,2,0,0,0",
            "2026-09-02,SYN-A,SYN-A-Z1,1000,1010,1,0,0,0",
            "2026-09-01,SYN-B,SYN-B-E,800,700,3,1,0,0",
        )
    )
    assert outcome.report.status == "valid"
    assert outcome.frame is not None
    assert outcome.report.row_count == 3
    assert outcome.report.mines == ["SYN-A", "SYN-B"]
    assert outcome.report.zones == ["SYN-A-Z1", "SYN-B-E"]
    assert outcome.report.date_min.isoformat() == "2026-09-01"
    assert outcome.report.date_max.isoformat() == "2026-09-02"
    assert outcome.report.series_count == 2
    assert outcome.report.rows_with_actual == 3


def test_missing_required_column_is_a_blocking_error() -> None:
    header = "date,mine_id,zone_id,planned_production_t,equipment_downtime_h"
    outcome = _validate(csv_text("2026-09-01,SYN-A,SYN-A-Z1,1000,2", header=header))
    assert outcome.report.status == "invalid"
    assert outcome.frame is None
    issue = next(i for i in outcome.report.issues if i.code == "missing_columns")
    assert "actual_production_t" in issue.message


def test_unknown_columns_are_ignored_with_a_warning() -> None:
    header = HEADER + ",operator_notes"
    outcome = _validate(csv_text("2026-09-01,SYN-A,SYN-A-Z1,1000,950,2,0,0,0,hello", header=header))
    assert outcome.report.status == "valid_with_warnings"
    assert "unknown_columns" in _codes(outcome)
    assert outcome.report.unknown_columns == ["operator_notes"]


def test_header_names_are_normalised_case_and_separators() -> None:
    header = "Date, Mine ID ,ZONE-ID,Planned_Production_T,actual_production_t"
    outcome = _validate(csv_text("2026-09-01,SYN-A,SYN-A-Z1,1000,950", header=header))
    assert outcome.report.status == "valid"
    assert outcome.frame is not None


def test_invalid_date_reports_the_file_line() -> None:
    outcome = _validate(
        csv_text(
            "2026-09-01,SYN-A,SYN-A-Z1,1000,950,2,0,0,0",
            "2026-13-40,SYN-A,SYN-A-Z1,1000,950,2,0,0,0",
        )
    )
    assert outcome.report.status == "invalid"
    issue = next(i for i in outcome.report.issues if i.code == "row_errors")
    assert any(example.startswith("line 3:") and "YYYY-MM-DD" in example for example in issue.examples)


def test_non_numeric_and_negative_values_are_rejected_with_reasons() -> None:
    outcome = _validate(
        csv_text(
            "2026-09-01,SYN-A,SYN-A-Z1,abc,950,2,0,0,0",
            "2026-09-02,SYN-A,SYN-A-Z1,1000,-5,2,0,0,0",
        )
    )
    assert outcome.report.status == "invalid"
    examples = next(i for i in outcome.report.issues if i.code == "row_errors").examples
    assert any("planned_production_t 'abc' is not a number" in e for e in examples)
    assert any("actual_production_t must be >= 0" in e for e in examples)


def test_hours_above_24_are_rejected() -> None:
    outcome = _validate(csv_text("2026-09-01,SYN-A,SYN-A-Z1,1000,950,25,0,0,0"))
    assert outcome.report.status == "invalid"
    examples = next(i for i in outcome.report.issues if i.code == "row_errors").examples
    assert any("equipment_downtime_h must be <= 24" in e for e in examples)


def test_blank_plan_is_a_blocking_error_but_blank_actual_is_pending() -> None:
    blank_plan = _validate(csv_text("2026-09-01,SYN-A,SYN-A-Z1,,950,2,0,0,0"))
    assert blank_plan.report.status == "invalid"
    assert "planned_production_t is required" in str(blank_plan.report.issues[-1].examples)

    pending = _validate(csv_text("2026-09-01,SYN-A,SYN-A-Z1,1000,,2,0,0,0"))
    assert pending.report.status == "valid_with_warnings"
    assert "pending_actuals" in _codes(pending)
    assert pending.frame is not None
    # Missing actuals are kept as NaN; they are never replaced by values.
    assert pending.frame["actual_production_t"].isna().all()
    assert pending.report.rows_pending_actual == 1


def test_duplicate_keys_are_rejected() -> None:
    outcome = _validate(
        csv_text(
            "2026-09-01,SYN-A,SYN-A-Z1,1000,950,2,0,0,0",
            "2026-09-01,SYN-A,SYN-A-Z1,1000,960,2,0,0,0",
        )
    )
    assert outcome.report.status == "invalid"
    assert "duplicate_rows" in _codes(outcome)


def test_wrong_number_of_cells_is_reported_by_line() -> None:
    outcome = _validate(csv_text("2026-09-01,SYN-A,SYN-A-Z1,1000,950,2,0,0,0,EXTRA"))
    assert outcome.report.status == "invalid"
    examples = next(i for i in outcome.report.issues if i.code == "row_errors").examples
    assert examples[0].startswith("line 2:") and "expected 9 columns" in examples[0]


def test_missing_calendar_days_are_reported_not_filled() -> None:
    outcome = _validate(
        csv_text(
            "2026-09-01,SYN-A,SYN-A-Z1,1000,950,2,0,0,0",
            "2026-09-04,SYN-A,SYN-A-Z1,1000,950,2,0,0,0",
        )
    )
    assert outcome.report.status == "valid_with_warnings"
    assert "date_gaps" in _codes(outcome)
    assert outcome.report.missing_date_gaps == 2
    assert outcome.frame is not None and len(outcome.frame) == 2


def test_iqr_outliers_are_flagged_but_kept() -> None:
    lines = [f"2026-09-{day:02d},SYN-A,SYN-A-Z1,1000,{900 + (day % 5) * 10},2,0,0,0" for day in range(1, 21)]
    lines.append("2026-10-01,SYN-A,SYN-A-Z1,1000,4000,2,0,0,0")
    outcome = _validate(csv_text(*lines))
    assert outcome.report.status == "valid_with_warnings"
    assert "outliers" in _codes(outcome)
    assert outcome.frame is not None
    assert 4000.0 in outcome.frame["actual_production_t"].tolist()


def test_actual_far_above_plan_is_a_warning() -> None:
    outcome = _validate(csv_text("2026-09-01,SYN-A,SYN-A-Z1,100,300,2,0,0,0"))
    assert "actual_far_above_plan" in _codes(outcome)


def test_empty_header_only_and_no_rows() -> None:
    outcome = _validate(csv_text(header=HEADER))
    assert outcome.report.status == "invalid"
    assert "no_rows" in _codes(outcome)


def test_too_many_rows_is_rejected() -> None:
    lines = [f"2026-09-{(i % 28) + 1:02d},SYN-A,SYN-A-Z{i},100,90,1,0,0,0" for i in range(5)]
    outcome = validate_production_csv(csv_text(*lines), max_rows=3, now=NOW)
    assert outcome.report.status == "invalid"
    assert "too_many_rows" in _codes(outcome)


def test_empty_bytes_raise_a_file_error() -> None:
    with pytest.raises(ProductionFileError, match="empty"):
        _validate(b"   \n")


def test_non_utf8_raises_a_file_error() -> None:
    with pytest.raises(ProductionFileError, match="UTF-8"):
        _validate("date,mine_id\n2026-09-01,\xe9".encode("latin-1"))


def test_duplicate_headers_raise_a_file_error() -> None:
    with pytest.raises(ProductionFileError, match="Duplicate column"):
        _validate(csv_text("2026-09-01,SYN-A", header="date,date"))


def test_bom_and_crlf_line_endings_are_accepted() -> None:
    raw = ("\ufeff" + HEADER + "\r\n2026-09-01,SYN-A,SYN-A-Z1,1000,950,2,0,0,0\r\n").encode("utf-8")
    outcome = _validate(raw)
    assert outcome.report.status == "valid"


def test_quoted_identifier_values_are_supported() -> None:
    outcome = _validate(csv_text('2026-09-01,"SYN-A","SYN-A-Z1",1000,950,2,0,0,0'))
    assert outcome.report.status == "valid"
