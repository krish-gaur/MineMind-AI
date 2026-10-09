"""Aggregates all API routers under the ``/api`` prefix."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import datasets, health, meta, overview

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(datasets.router)
api_router.include_router(overview.router)
api_router.include_router(meta.router)
