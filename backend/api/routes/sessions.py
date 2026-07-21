"""Game session and command REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.schemas.models import (
    AdvanceRequest,
    AdvanceResponse,
    CommandRequest,
    CommandResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    SessionSummaryResponse,
    SnapshotResponse,
)
from backend.dependencies import Services, get_services
from backend.errors import ApiError, ErrorCode

router = APIRouter(tags=["game-sessions"])


@router.post("/game-sessions", response_model=CreateSessionResponse, status_code=201)
async def create_session(
    body: CreateSessionRequest, services: Services = Depends(get_services)
) -> CreateSessionResponse:
    result = await services.session_service.create_session(seed=body.seed, users=body.users)
    return CreateSessionResponse(**result)


@router.get("/game-sessions/{session_id}", response_model=SessionSummaryResponse)
async def get_session(
    session_id: str, services: Services = Depends(get_services)
) -> SessionSummaryResponse:
    result = await services.session_service.get_summary(session_id)
    return SessionSummaryResponse(**result)


@router.get("/game-sessions/{session_id}/snapshot", response_model=SnapshotResponse)
async def get_snapshot(
    session_id: str, services: Services = Depends(get_services)
) -> SnapshotResponse:
    result = await services.session_service.get_snapshot(session_id)
    return SnapshotResponse(**result)


@router.post("/game-sessions/{session_id}/commands", response_model=CommandResponse)
async def post_command(
    session_id: str, body: CommandRequest, services: Services = Depends(get_services)
) -> CommandResponse:
    result = await services.command_service.apply_command(
        session_id,
        command_id=body.command_id,
        command_type=body.command_type,
        payload=body.payload,
        expected_revision=body.expected_revision,
    )
    return CommandResponse(**result)


# Development/internal only: guarded by ENABLE_MANUAL_TICK_API (default false).
internal_router = APIRouter(tags=["internal"])


@internal_router.post("/game-sessions/{session_id}/advance", response_model=AdvanceResponse)
async def advance_session(
    session_id: str, body: AdvanceRequest, services: Services = Depends(get_services)
) -> AdvanceResponse:
    if not services.settings.enable_manual_tick_api:
        raise ApiError(
            ErrorCode.MANUAL_TICK_DISABLED,
            "Manual tick advance is disabled.",
        )
    if body.ticks > services.settings.max_ticks_per_request:
        raise ApiError(
            ErrorCode.VALIDATION_ERROR,
            "ticks exceeds the configured per-request limit.",
            details={"max_ticks_per_request": services.settings.max_ticks_per_request},
        )
    result = await services.command_service.advance_session(
        session_id, ticks=body.ticks, expected_revision=body.expected_revision
    )
    return AdvanceResponse(**result)
