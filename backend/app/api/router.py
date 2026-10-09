"""Aggregates all API routers under the ``/api`` prefix."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import datasets, exploration, forecast, geo, health, meta, overview, recommendations

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(datasets.router)
api_router.include_router(overview.router)
api_router.include_router(forecast.router)
api_router.include_router(recommendations.router)
api_router.include_router(geo.router)
api_router.include_router(exploration.router)
api_router.include_router(meta.router)
