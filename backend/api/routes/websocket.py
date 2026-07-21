"""WebSocket route."""

from __future__ import annotations

from fastapi import APIRouter
from starlette.websockets import WebSocket

from backend.dependencies import get_services
from backend.websocket.manager import handle_connection

router = APIRouter()


@router.websocket("/ws/v1/game-sessions/{session_id}")
async def game_session_ws(websocket: WebSocket, session_id: str, after_cursor: int = 0) -> None:
    services = get_services(websocket)
    await handle_connection(websocket, session_id, after_cursor, services)
