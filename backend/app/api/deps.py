"""FastAPI dependencies shared by routers."""

from __future__ import annotations

from fastapi import Request

from app.config import Settings
from app.domain.store import DatasetStore


def get_store(request: Request) -> DatasetStore:
    store: DatasetStore = request.app.state.store
    return store


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings
