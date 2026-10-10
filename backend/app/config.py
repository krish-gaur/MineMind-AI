"""Environment-based configuration.

Every setting can be overridden with an environment variable of the same name
(upper-case), or placed in ``backend/.env`` for local development. Secrets are
never required: the public satellite and weather services used by MineMind AI
are keyless. Any future credential must be supplied via the environment only.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime settings. See ``backend/.env.example`` for documentation."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # CORS: comma-separated list of exact origins, plus an optional regex
    # (useful for Vercel preview deployments, e.g. https://.*\.vercel\.app).
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cors_origin_regex: str = ""

    # Storage. On Render the filesystem is ephemeral; the synthetic demo data is
    # regenerated deterministically at startup, but user uploads are not kept
    # across redeploys unless DATA_DIR points at a persistent disk.
    data_dir: Path = Field(default=BACKEND_DIR / "data_store")
    artifacts_dir: Path = Field(default=BACKEND_DIR / "artifacts")

    # Upload limits (defence against oversized or abusive inputs).
    max_upload_mb: float = Field(default=5.0, gt=0, le=50)
    max_upload_rows: int = Field(default=50_000, gt=0, le=500_000)

    # Freshness policy: data whose last actual record is older than this many
    # days is flagged as stale on the dashboard.
    stale_data_days: int = Field(default=14, ge=1)

    # External public services (all keyless). Set ENABLE_EXTERNAL_SERVICES=false
    # to force the offline fallback path, e.g. in CI.
    enable_external_services: bool = True
    external_timeout_s: float = Field(default=8.0, gt=0, le=60)
    external_cache_ttl_h: float = Field(default=24.0, ge=0)
    cdse_stac_url: str = "https://stac.dataspace.copernicus.eu/v1"
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"

    # Forecasting.
    forecast_horizon_days: int = Field(default=30, ge=7, le=90)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings object (cached)."""
    return Settings()
