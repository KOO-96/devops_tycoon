"""Backend configuration via environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEVOPS_TYCOON_", extra="ignore")

    # Storage / broker selection. "memory" needs no external services and is the
    # default for local/dev/test; "postgres"/"redis" are used in real deploys.
    storage_backend: Literal["memory", "postgres"] = "memory"
    event_broker: Literal["memory", "redis"] = "memory"

    database_url: str = "postgresql+asyncpg://localhost/devops_tycoon"
    redis_url: str = "redis://localhost:6379/0"

    # Command / tick limits.
    max_ticks_per_request: int = Field(default=100, ge=1)

    # Development-only manual tick advance endpoint (disabled by default).
    enable_manual_tick_api: bool = False

    # Event query paging.
    events_page_default: int = Field(default=100, ge=1)
    events_page_max: int = Field(default=1000, ge=1)

    app_name: str = "devops-tycoon-backend"
    api_prefix: str = "/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
