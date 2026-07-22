"""FastAPI application factory and lifespan wiring."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.adapters.event_broker import EventBroker, InMemoryEventBroker
from backend.adapters.simulation_adapter import SimulationAdapter
from backend.api.routes import events as events_routes
from backend.api.routes import health as health_routes
from backend.api.routes import sessions as sessions_routes
from backend.api.routes import websocket as websocket_routes
from backend.application.command_service import CommandService
from backend.application.event_service import EventQueryService
from backend.application.game_session_service import GameSessionService
from backend.config import Settings, get_settings
from backend.dependencies import Services
from backend.errors import ApiError, ErrorCode
from backend.middleware.request_id import request_id_middleware
from backend.persistence.memory import MemoryUnitOfWorkFactory
from backend.persistence.repositories import UnitOfWorkFactory


def _build_storage(settings: Settings) -> tuple[UnitOfWorkFactory, Any]:
    """Return (uow_factory, storage_ping | None)."""
    factory: UnitOfWorkFactory
    if settings.storage_backend == "postgres":
        from backend.persistence.postgres import build_postgres_storage

        factory, ping = build_postgres_storage(settings.database_url)
        return factory, ping
    factory = MemoryUnitOfWorkFactory()
    return factory, None


def _build_broker(settings: Settings) -> EventBroker:
    if settings.event_broker == "redis":
        from backend.adapters.event_broker import RedisEventBroker

        return RedisEventBroker(settings.redis_url)
    return InMemoryEventBroker()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        uow_factory, storage_ping = _build_storage(settings)
        broker = _build_broker(settings)
        adapter = SimulationAdapter()
        app.state.services = Services(
            settings=settings,
            session_service=GameSessionService(uow_factory, adapter),
            command_service=CommandService(uow_factory, adapter, broker),
            event_query_service=EventQueryService(
                uow_factory,
                default_limit=settings.events_page_default,
                max_limit=settings.events_page_max,
            ),
            broker=broker,
        )
        app.state.storage_ping = storage_ping
        try:
            yield
        finally:
            closer = getattr(uow_factory, "aclose", None)
            if closer is not None:
                await closer()

    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
    app.middleware("http")(request_id_middleware)
    _register_exception_handlers(app)

    app.include_router(health_routes.router)
    app.include_router(sessions_routes.router, prefix=settings.api_prefix)
    app.include_router(events_routes.router, prefix=settings.api_prefix)
    app.include_router(sessions_routes.internal_router, prefix="/internal/v1")
    app.include_router(websocket_routes.router)
    return app


def _register_exception_handlers(app: FastAPI) -> None:
    def _request_id(request: Request) -> str:
        return getattr(request.state, "request_id", "unknown")

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=exc.to_envelope(_request_id(request))
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        err = ApiError(
            ErrorCode.VALIDATION_ERROR,
            "Request validation failed.",
            details={"errors": _safe_validation_details(exc)},
        )
        return JSONResponse(
            status_code=err.status_code, content=err.to_envelope(_request_id(request))
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        err = ApiError(ErrorCode.INTERNAL_ERROR, "An internal error occurred.")
        return JSONResponse(
            status_code=err.status_code, content=err.to_envelope(_request_id(request))
        )


def _safe_validation_details(exc: RequestValidationError) -> list[dict[str, Any]]:
    # Expose location/type only; never echo internal objects or values verbatim.
    out: list[dict[str, Any]] = []
    for e in exc.errors():
        out.append({"loc": [str(p) for p in e.get("loc", [])], "type": e.get("type", "")})
    return out
