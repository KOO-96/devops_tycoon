"""Event query endpoint (PostgreSQL-backed cursor pagination)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.schemas.error_responses import READ_SESSION_RESPONSES
from backend.api.schemas.models import EventEnvelope, EventListResponse
from backend.dependencies import Services, get_services

router = APIRouter(tags=["events"])


@router.get(
    "/game-sessions/{session_id}/events",
    response_model=EventListResponse,
    responses=READ_SESSION_RESPONSES,
)
async def list_events(
    session_id: str,
    after_cursor: int = Query(
        default=0,
        ge=0,
        description="Exclusive cursor; returns events with cursor > this value.",
    ),
    limit: int | None = Query(
        default=None,
        ge=1,
        description=(
            "Max events to return. Defaults to 100, capped at 1000. If the result "
            "count equals the effective limit, request the next page using the last "
            "event's cursor as after_cursor. Cursors are globally monotonic, so a "
            "session's cursors ascend but may have gaps (not lost events)."
        ),
    ),
    services: Services = Depends(get_services),
) -> EventListResponse:
    envelopes = await services.event_query_service.list_events(
        session_id, after_cursor=after_cursor, limit=limit
    )
    return EventListResponse(
        session_id=session_id,
        events=[EventEnvelope(**e) for e in envelopes],
    )
