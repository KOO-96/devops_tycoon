"""Event query endpoint (PostgreSQL-backed cursor pagination)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.schemas.models import EventEnvelope, EventListResponse
from backend.dependencies import Services, get_services

router = APIRouter(tags=["events"])


@router.get("/game-sessions/{session_id}/events", response_model=EventListResponse)
async def list_events(
    session_id: str,
    after_cursor: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1),
    services: Services = Depends(get_services),
) -> EventListResponse:
    envelopes = await services.event_query_service.list_events(
        session_id, after_cursor=after_cursor, limit=limit
    )
    return EventListResponse(
        session_id=session_id,
        events=[EventEnvelope(**e) for e in envelopes],
    )
