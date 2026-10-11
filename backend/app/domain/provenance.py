"""Source-type and value-kind labels.

Two independent questions are answered for every number the platform shows:

* ``SourceType``  - where did the underlying records come from?
  (synthetic demonstration, user-provided, or a public dataset)
* ``ValueKind``   - what kind of number is it?
  (measured record, model forecast, probability, arithmetic estimate, scenario,
  transparent rule output, or expert-weighted index)

Keeping these separate lets the UI and the report say, for example,
"FORECAST computed from SYNTHETIC DEMONSTRATION DATA".
"""

from __future__ import annotations

from enum import StrEnum


class SourceType(StrEnum):
    SYNTHETIC = "synthetic"
    USER_PROVIDED = "user_provided"
    PUBLIC = "public"


class ValueKind(StrEnum):
    MEASURED = "measured"
    FORECAST = "forecast"
    PROBABILITY = "probability"
    ESTIMATE = "estimate"
    SCENARIO = "scenario"
    RULE_BASED = "rule_based"
    INDEX = "index"


SOURCE_LABELS: dict[SourceType, str] = {
    SourceType.SYNTHETIC: "SYNTHETIC DEMONSTRATION DATA",
    SourceType.USER_PROVIDED: "USER-PROVIDED DATA (not verified by MineMind)",
    SourceType.PUBLIC: "PUBLIC DATA",
}

VALUE_KIND_LABELS: dict[ValueKind, str] = {
    ValueKind.MEASURED: "Measured (recorded value)",
    ValueKind.FORECAST: "Forecast (regression model output)",
    ValueKind.PROBABILITY: "Probability (classifier output)",
    ValueKind.ESTIMATE: "Estimate (arithmetic on stated assumptions)",
    ValueKind.SCENARIO: "Scenario (assumption-driven projection)",
    ValueKind.RULE_BASED: "Rule-based (transparent policy thresholds, not learned)",
    ValueKind.INDEX: "Index (expert-weighted, not a probability)",
}

SYNTHETIC_BANNER = (
    "Synthetic demonstration data. Not MOIL operational records. "
    "Results illustrate the workflow only and are not evidence of real-world performance."
)


def source_label(source_type: SourceType | str) -> str:
    return SOURCE_LABELS[SourceType(source_type)]


def is_synthetic(source_type: SourceType | str) -> bool:
    return SourceType(source_type) is SourceType.SYNTHETIC
