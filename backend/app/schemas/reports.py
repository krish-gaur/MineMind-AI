"""Request model for report generation."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

SectionName = Literal["overview", "forecast", "risk", "recommendations", "exploration", "sources"]
ALL_SECTION_NAMES: list[SectionName] = [
    "overview",
    "forecast",
    "risk",
    "recommendations",
    "exploration",
    "sources",
]


class ReportRequest(BaseModel):
    dataset_id: str | None = Field(default=None, max_length=80)
    mine_id: str | None = Field(default=None, max_length=40)
    zone_id: str | None = Field(default=None, max_length=40)
    start: date | None = None
    end: date | None = None
    horizon_days: int = Field(default=30, ge=7, le=90)
    sections: list[SectionName] = Field(default_factory=lambda: list(ALL_SECTION_NAMES), min_length=1)
    format: Literal["html", "json"] = "html"
    title: str = Field(default="MineMind AI report", min_length=1, max_length=120)
    zones_dataset_id: str | None = Field(default=None, max_length=80)
    drillholes_dataset_id: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def _check_dates(self) -> ReportRequest:
        if self.start and self.end and self.start > self.end:
            raise ValueError("start must be on or before end")
        return self
