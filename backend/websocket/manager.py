"""WebSocket connection handler.

Handshake ordering closes the replay->live gap (HIGH-2):

1. verify session
2. **subscribe to the broker first** and pump live events into a buffer
3. replay durable events from PostgreSQL (source of truth) with cursor > after_cursor
4. send SESSION_STATE
5. one **catch-up** query from PostgreSQL (covers events committed during replay
   and events whose Redis publish failed)
6. switch to live, de-duplicating by cursor (<= last_delivered are dropped)

Because the subscription is active before replay, any event published during the
handshake is buffered; the catch-up query recovers events that were committed but
not (successfully) published; cursor de-duplication prevents double delivery.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

from starlette.websockets import WebSocket, WebSocketDisconnect

from backend.dependencies import Services
from backend.errors import ApiError
from backend.websocket.protocol import MessageType, message

_REPLAY_PAGE = 500
_HEARTBEAT_TIMEOUT = 15.0


async def handle_connection(
    websocket: WebSocket, session_id: str, after_cursor: int, services: Services
) -> None:
    await websocket.accept()

    try:
        summary = await services.session_service.get_summary(session_id)
    except ApiError as exc:
        await websocket.send_json(
            message(
                MessageType.ERROR,
                session_id,
                {"code": exc.code.value, "message": exc.message},
            )
        )
        await websocket.close()
        return

    subscription = services.broker.subscribe(session_id)
    async with subscription as live_iter:
        live_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        pump = asyncio.create_task(_pump(live_iter, live_queue))
        try:
            last = after_cursor
            last = await _drain_durable(websocket, services, session_id, last)  # replay
            await websocket.send_json(message(MessageType.SESSION_STATE, session_id, summary))
            last = await _drain_durable(websocket, services, session_id, last)  # catch-up
            await _live_loop(websocket, session_id, live_queue, last)
        finally:
            pump.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pump


async def _pump(
    live_iter: AsyncIterator[dict[str, Any]], queue: asyncio.Queue[dict[str, Any]]
) -> None:
    async for env in live_iter:
        await queue.put(env)


async def _drain_durable(
    websocket: WebSocket, services: Services, session_id: str, cursor: int
) -> int:
    """Send all durable events with cursor > `cursor`; return the new max cursor."""
    while True:
        page = await services.event_query_service.list_events(
            session_id, after_cursor=cursor, limit=_REPLAY_PAGE
        )
        if not page:
            return cursor
        for env in page:
            c = int(env["cursor"])
            await websocket.send_json(message(MessageType.DOMAIN_EVENT, session_id, env, cursor=c))
            cursor = max(cursor, c)
        if len(page) < _REPLAY_PAGE:
            return cursor


async def _live_loop(
    websocket: WebSocket, session_id: str, queue: asyncio.Queue[dict[str, Any]], last: int
) -> None:
    stop = asyncio.Event()
    reader = asyncio.create_task(_drain_client(websocket, stop))
    stop_task = asyncio.ensure_future(stop.wait())
    try:
        while not stop.is_set():
            get_task = asyncio.ensure_future(queue.get())
            done, _pending = await asyncio.wait(
                {get_task, stop_task},
                timeout=_HEARTBEAT_TIMEOUT,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stop.is_set():
                get_task.cancel()
                break
            if get_task not in done:
                get_task.cancel()  # safe: no item was dequeued
                await websocket.send_json(message(MessageType.HEARTBEAT, session_id, {}))
                continue
            env = get_task.result()
            cursor = int(env.get("cursor", 0))
            if cursor <= last:
                continue  # already delivered via replay/catch-up (dedup)
            await websocket.send_json(
                message(MessageType.DOMAIN_EVENT, session_id, env, cursor=cursor)
            )
            last = cursor
    finally:
        stop_task.cancel()
        reader.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reader
        with contextlib.suppress(asyncio.CancelledError):
            await stop_task


async def _drain_client(websocket: WebSocket, stop: asyncio.Event) -> None:
    """Detect client disconnect (inbound messages are ignored in MVP)."""
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        stop.set()
