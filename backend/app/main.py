"""FastAPI application factory.

Run locally::

    uvicorn app.main:app --reload --port 8000

Interactive API docs: http://127.0.0.1:8000/api/docs
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.config import Settings, get_settings
from app.domain.forecast_service import ForecastService
from app.domain.ingest import ensure_demo_dataset
from app.domain.store import DatasetStore
from app.errors import register_exception_handlers
from app.logging_config import configure_logging, get_logger
from app.middleware import request_context

log = get_logger("minemind.app")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        store: DatasetStore = application.state.store
        store.ensure_dirs()
        manifest = ensure_demo_dataset(store)
        log.info(
            "startup complete",
            extra={"event": "startup", "dataset_id": manifest.id, "source": manifest.source_type},
        )
        yield

    application = FastAPI(
        title="MineMind AI API",
        version=__version__,
        description=(
            "Manganese exploration and production intelligence for SIH26009. "
            "Synthetic demonstration data is labelled wherever it is used."
        ),
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    application.state.settings = settings
    application.state.store = DatasetStore(settings.data_dir)
    application.state.forecast = ForecastService(
        application.state.store,
        settings.artifacts_dir,
        horizon_days=settings.forecast_horizon_days,
    )

    register_exception_handlers(application)
    # Added first so it sits inside CORS: error responses still carry CORS headers.
    application.middleware("http")(request_context)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Content-Disposition"],
        max_age=600,
    )
    application.include_router(api_router, prefix="/api")
    return application


app = create_app()
