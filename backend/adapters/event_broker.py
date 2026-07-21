"""Event broker for live WebSocket fan-out.

The broker is a *transport* only. PostgreSQL (game_events) is the source of
truth; a publish failure must never roll back a committed transaction, and any
committed event is recoverable via the event cursor API.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EventBroker(Protocol):
    async def publish(self, session_id: str, envelope: dict[str, Any]) -> None: ...
    def subscribe(self, session_id: str) -> AbstractSubscription: ...
    async def ping(self) -> bool: ...


@runtime_checkable
class AbstractSubscription(Protocol):
    async def __aenter__(self) -> AsyncIterator[dict[str, Any]]: ...
    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None: ...


class _MemorySubscription:
    def __init__(self, broker: InMemoryEventBroker, session_id: str) -> None:
        self._broker = broker
        self._session_id = session_id
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def __aenter__(self) -> AsyncIterator[dict[str, Any]]:
        self._broker._subscribers.setdefault(self._session_id, set()).add(self._queue)
        return self._iter()

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        subs = self._broker._subscribers.get(self._session_id)
        if subs is not None:
            subs.discard(self._queue)
            if not subs:
                self._broker._subscribers.pop(self._session_id, None)

    async def _iter(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            yield await self._queue.get()


class InMemoryEventBroker:
    """Single-process broker (default). Not for multi-instance deploys."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}

    async def publish(self, session_id: str, envelope: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(session_id, set())):
            queue.put_nowait(envelope)

    def subscribe(self, session_id: str) -> _MemorySubscription:
        return _MemorySubscription(self, session_id)

    async def ping(self) -> bool:
        return True


class _RedisSubscription:
    def __init__(self, broker: RedisEventBroker, session_id: str) -> None:
        self._broker = broker
        self._channel = broker._channel(session_id)
        self._pubsub: Any = None

    async def __aenter__(self) -> AsyncIterator[dict[str, Any]]:
        self._pubsub = self._broker._client.pubsub()
        await self._pubsub.subscribe(self._channel)
        return self._iter()

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._pubsub is not None:
            with contextlib.suppress(Exception):
                await self._pubsub.unsubscribe(self._channel)
                await self._pubsub.aclose()

    async def _iter(self) -> AsyncIterator[dict[str, Any]]:
        async for message in self._pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message.get("data")
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            yield json.loads(data)


class RedisEventBroker:
    """Cross-instance pub/sub via redis-py asyncio. Transport only."""

    def __init__(self, redis_url: str) -> None:
        import redis.asyncio as aioredis

        # redis-py's from_url is untyped; the async client is used dynamically.
        self._client: Any = aioredis.from_url(redis_url)  # type: ignore[no-untyped-call]

    @staticmethod
    def _channel(session_id: str) -> str:
        return f"devops_tycoon:events:{session_id}"

    async def publish(self, session_id: str, envelope: dict[str, Any]) -> None:
        await self._client.publish(self._channel(session_id), json.dumps(envelope))

    def subscribe(self, session_id: str) -> _RedisSubscription:
        return _RedisSubscription(self, session_id)

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception:  # noqa: BLE001 - readiness probe must not raise
            return False
