"""Application errors and the consistent JSON error envelope.

Every error response has the shape::

    {"error": {"code": "...", "message": "...", "details": ..., "request_id": "..."}}

Stack traces are logged server-side only and are never returned to clients.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import get_logger

log = get_logger("minemind.errors")


class AppError(Exception):
    """Base class for expected, user-facing errors."""

    status_code: int = 400
    code: str = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


class UnsupportedMediaError(AppError):
    status_code = 415
    code = "unsupported_media_type"


class ValidationFailedError(AppError):
    """A dataset or payload failed validation. ``details`` carries the report."""

    status_code = 422
    code = "validation_failed"


class InsufficientDataError(AppError):
    """The dataset does not contain enough records for the requested analysis."""

    status_code = 422
    code = "insufficient_data"


class ExternalServiceError(AppError):
    """A public external service is unavailable. The caller decides on fallback."""

    status_code = 503
    code = "external_service_unavailable"


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _envelope(request: Request, status_code: int, code: str, message: str, details: Any = None) -> JSONResponse:
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": _request_id(request),
        }
    }
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


_HTTP_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_failed",
    429: "rate_limited",
}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers that convert every error into the standard envelope."""

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            log.error("application error", extra={"error_code": exc.code})
        return _envelope(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        message = str(exc.detail) if exc.detail else "Request failed."
        return _envelope(request, exc.status_code, code, message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        problems = [
            {
                "field": ".".join(str(part) for part in err.get("loc", ())[1:]) or "body",
                "message": str(err.get("msg", "Invalid value.")),
            }
            for err in exc.errors()
        ]
        return _envelope(
            request,
            422,
            "validation_failed",
            "The request could not be processed. Check the highlighted fields.",
            details=problems,
        )
