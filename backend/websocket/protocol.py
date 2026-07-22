"""WebSocket message protocol.

Every message carries `protocol_version`, `message_type`, `session_id`, `cursor`,
and `payload`. Domain events keep their backend `event_id`/`cursor` so clients
can de-duplicate at-least-once delivery.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

PROTOCOL_VERSION = 1


class MessageType(StrEnum):
    SESSION_SNAPSHOT = "SESSION_SNAPSHOT"
    SESSION_STATE = "SESSION_STATE"
    DOMAIN_EVENT = "DOMAIN_EVENT"
    COMMAND_RESULT = "COMMAND_RESULT"
    ERROR = "ERROR"
    HEARTBEAT = "HEARTBEAT"


def message(
    message_type: MessageType,
    session_id: str,
    payload: dict[str, Any],
    *,
    cursor: int = 0,
) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "message_type": message_type.value,
        "session_id": session_id,
        "cursor": cursor,
        "payload": payload,
    }
