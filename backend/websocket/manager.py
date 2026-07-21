"""WebSocket connection handler: replay-on-connect + live fan-out."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from starlette.websockets import WebSocket, WebSocketDisconnect

from backend.dependencies import Services
from backend.errors import ApiError
from backend.websocket.protocol import MessageType, message

_REPLAY_PAGE = 500


async def handle_connection(
    websocket: WebSocket, session_id: str, after_cursor: int, services: Services
) -> None:
    await websocket.accept()

    # 1. Verify session exists; send current state summary.
    try:
        summary = await services.session_service.get_summary(session_id)
    except ApiError as exc:
        await websocket.send_json(
            message(MessageType.ERROR, session_id, {"code": exc.code.value, "message": exc.message})
        )
        await websocket.close()
        return

    # 2. Replay missed events from the durable store (source of truth).
    cursor = after_cursor
    while True:
        page = await services.event_query_service.list_events(
            session_id, after_cursor=cursor, limit=_REPLAY_PAGE
        )
        if not page:
            break
        for env in page:
            await websocket.send_json(
                message(MessageType.DOMAIN_EVENT, session_id, env, cursor=int(env["cursor"]))
            )
            cursor = max(cursor, int(env["cursor"]))
        if len(page) < _REPLAY_PAGE:
            break

    # 3. Current state summary after replay.
    await websocket.send_json(message(MessageType.SESSION_STATE, session_id, summary))

    # 4. Live events + heartbeat until the client disconnects.
    await _stream_live(websocket, session_id, services)


async def _stream_live(websocket: WebSocket, session_id: str, services: Services) -> None:
    subscription = services.broker.subscribe(session_id)
    async with subscription as events:
        stop = asyncio.Event()
        reader = asyncio.create_task(_drain_client(websocket, stop))
        try:
            while not stop.is_set():
                try:
                    env = await asyncio.wait_for(anext(events), timeout=15.0)
                except TimeoutError:
                    await websocket.send_json(message(MessageType.HEARTBEAT, session_id, {}))
                    continue
                except (StopAsyncIteration, WebSocketDisconnect):
                    break
                await websocket.send_json(
                    message(
                        MessageType.DOMAIN_EVENT, session_id, env, cursor=int(env.get("cursor", 0))
                    )
                )
        finally:
            reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reader


async def _drain_client(websocket: WebSocket, stop: asyncio.Event) -> None:
    """Detect client disconnect (we do not process inbound messages in MVP)."""
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        stop.set()


def payload_of(env: dict[str, Any]) -> dict[str, Any]:
    return env
