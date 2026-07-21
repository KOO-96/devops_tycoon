"""Liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from simulation.state import STATE_VERSION
from starlette.requests import Request

from backend.api.schemas.models import HealthResponse, ReadinessComponent, ReadinessResponse
from backend.dependencies import Services, get_services

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    # Liveness must not depend on external stores.
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=ReadinessResponse)
async def ready(
    response: Response,
    request: Request,
    services: Services = Depends(get_services),
) -> ReadinessResponse:
    components: dict[str, ReadinessComponent] = {}

    broker_ok = await services.broker.ping()
    components["event_broker"] = ReadinessComponent(ok=broker_ok)

    checker = getattr(request.app.state, "storage_ping", None)
    if checker is not None:
        try:
            db_ok = await checker()
        except Exception:  # noqa: BLE001 - readiness probe never raises
            db_ok = False
        components["database"] = ReadinessComponent(ok=db_ok)
    else:
        components["database"] = ReadinessComponent(ok=True, detail="in-memory")

    all_ok = all(c.ok for c in components.values())
    if not all_ok:
        response.status_code = 503
    return ReadinessResponse(
        status="ok" if all_ok else "degraded",
        components=components,
        supported_state_version=STATE_VERSION,
    )
