"""Registry of data sources and how MineMind AI uses them.

The registry is the single place where licences, attributions and limitations
are recorded. It is served at ``GET /api/meta/sources`` and shown in the UI and
in every generated report.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.domain.provenance import SourceType


@dataclass(frozen=True)
class DataSource:
    id: str
    name: str
    provider: str
    source_type: SourceType
    url: str
    access: str
    licence: str
    attribution: str
    used_for: str
    limitations: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["source_type"] = self.source_type.value
        data["limitations"] = list(self.limitations)
        return data


SOURCES: tuple[DataSource, ...] = (
    DataSource(
        id="synthetic_production",
        name="Synthetic production records (SYN-A/B/C)",
        provider="MineMind AI generator (seed 26009)",
        source_type=SourceType.SYNTHETIC,
        url="",
        access="Generated locally by backend/app/domain/synthetic.py",
        licence="Not applicable",
        attribution="Synthetic demonstration data generated for SIH26009 prototype.",
        used_for="Daily planned/actual production, downtime, weather and blasting delays for the demo.",
        limitations=(
            "Not MOIL operational data.",
            "Parameters are illustrative; no calibration to any real mine.",
            "Built-in relationships are generator design choices, not discoveries.",
        ),
    ),
    DataSource(
        id="copernicus_sentinel2",
        name="Copernicus Sentinel-2 L2A scene catalogue",
        provider="European Space Agency / Copernicus Data Space Ecosystem (CDSE)",
        source_type=SourceType.PUBLIC,
        url="https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a",
        access="Keyless STAC search (bbox and datetime). Only scene metadata and footprints are used.",
        licence="Copernicus Sentinel data: free, full and open access under the EU Copernicus data policy.",
        attribution="Contains modified Copernicus Sentinel data [year] (when imagery is displayed).",
        used_for="Acquisition dates, footprints and cloud cover of Sentinel-2 scenes over the study area.",
        limitations=(
            "Metadata only: no band values or indices are computed in this release.",
            "Cloud cover is the scene-level estimate reported by the catalogue.",
            "Availability depends on the public catalogue being reachable from the server.",
        ),
    ),
    DataSource(
        id="open_meteo_archive",
        name="Open-Meteo historical weather (ERA5 reanalysis)",
        provider="Open-Meteo.com (ERA5 reanalysis, ECMWF/Copernicus Climate Change Service)",
        source_type=SourceType.PUBLIC,
        url="https://open-meteo.com/en/docs/historical-weather-api",
        access="Keyless HTTP GET. Free for non-commercial use (fair-use limits apply).",
        licence="Open-Meteo data: CC BY 4.0. Commercial use requires a paid Open-Meteo plan.",
        attribution=("Weather data by Open-Meteo.com (CC BY 4.0). ERA5 data: Copernicus Climate Change Service."),
        used_for="Daily precipitation at a site coordinate, used to enrich rainfall where requested.",
        limitations=(
            "Reanalysis grid cell, not a station measurement at the mine.",
            "Daily totals only; no intraday timing.",
            "Availability depends on the public API being reachable from the server.",
        ),
    ),
    DataSource(
        id="natural_earth_countries",
        name="Natural Earth country boundaries (110m, via world-atlas)",
        provider="Natural Earth (public domain); packaged by the world-atlas npm module (ISC)",
        source_type=SourceType.PUBLIC,
        url="https://www.naturalearthdata.com/",
        access="Bundled static GeoJSON used for the offline basemap outline.",
        licence="Public domain (Natural Earth terms of use).",
        attribution="Made with Natural Earth.",
        used_for="Country outline for context on the map when no online basemap is configured.",
        limitations=("Generalised 1:110m geometry; not suitable for survey or boundary decisions.",),
    ),
)


def list_sources() -> list[dict[str, object]]:
    return [source.as_dict() for source in SOURCES]
