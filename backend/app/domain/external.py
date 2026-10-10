"""Keyless public-service client with a disk cache and explicit degradation.

Every call returns a :class:`ServiceResult` and never raises for network or content problems. The
``status`` tells the caller exactly what was obtained:

* ``live``        - fetched now from the public service;
* ``cached``      - a previous successful response, still within the TTL;
* ``unavailable`` - the service could not be reached or returned unusable content (message says why);
* ``disabled``    - external services are turned off by configuration (offline demonstration mode).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from app.logging_config import get_logger

log = get_logger("minemind.external")


@dataclass(frozen=True)
class ServiceResult:
    status: str
    data: Any
    retrieved_at: datetime | None
    message: str

    @property
    def ok(self) -> bool:
        return self.status in {"live", "cached"}


class PublicJsonClient:
    def __init__(
        self,
        *,
        cache_dir: Path,
        ttl_hours: float,
        timeout_s: float,
        enabled: bool,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._cache_dir = Path(cache_dir)
        self._ttl = timedelta(hours=ttl_hours)
        self._timeout = timeout_s
        self._enabled = enabled
        self._transport = transport

    def _cache_path(self, key: str) -> Path:
        return self._cache_dir / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()}.json"

    def get_json(self, url: str, params: dict[str, Any], *, cache_key: str, service: str) -> ServiceResult:
        if not self._enabled:
            return ServiceResult("disabled", None, None, f"{service} is disabled by configuration.")

        path = self._cache_path(cache_key)
        now = datetime.now(UTC)
        if path.exists():
            try:
                cached = json.loads(path.read_text(encoding="utf-8"))
                retrieved = datetime.fromisoformat(cached["retrieved_at"])
                if now - retrieved <= self._ttl:
                    return ServiceResult(
                        "cached", cached["data"], retrieved, f"Cached response from {service} (fetched earlier)."
                    )
            except (KeyError, ValueError, json.JSONDecodeError):
                path.unlink(missing_ok=True)

        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport, follow_redirects=False) as client:
                response = client.get(url, params=params, headers={"Accept": "application/json"})
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            log.warning("external timeout", extra={"source": service, "event": "external_timeout"})
            return ServiceResult("unavailable", None, None, f"{service} did not respond in time.")
        except httpx.HTTPStatusError as exc:
            log.warning(
                "external http error",
                extra={"source": service, "event": "external_http_error", "status": exc.response.status_code},
            )
            return ServiceResult("unavailable", None, None, f"{service} returned HTTP {exc.response.status_code}.")
        except httpx.HTTPError as exc:
            log.warning(
                "external request failed",
                extra={"source": service, "event": "external_request_failed", "error_code": exc.__class__.__name__},
            )
            return ServiceResult("unavailable", None, None, f"{service} could not be reached from this server.")
        except ValueError:
            return ServiceResult("unavailable", None, None, f"{service} returned content that is not JSON.")

        self._cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"retrieved_at": now.isoformat(), "data": data}), encoding="utf-8")
        return ServiceResult("live", data, now, f"Fetched from {service} just now.")
