"""Structured API error contract.

All REST errors serialize to a single stable envelope so clients never parse
natural-language messages. Internal details (stack traces, DB internals) are
never exposed.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    REVISION_CONFLICT = "REVISION_CONFLICT"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    COMMAND_OUT_OF_ORDER = "COMMAND_OUT_OF_ORDER"
    COMMAND_REJECTED = "COMMAND_REJECTED"
    SNAPSHOT_VERSION_UNSUPPORTED = "SNAPSHOT_VERSION_UNSUPPORTED"
    MANUAL_TICK_DISABLED = "MANUAL_TICK_DISABLED"
    SIMULATION_EXECUTION_FAILED = "SIMULATION_EXECUTION_FAILED"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    EVENT_BROKER_UNAVAILABLE = "EVENT_BROKER_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# Default HTTP status per error code.
HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.SESSION_NOT_FOUND: 404,
    ErrorCode.REVISION_CONFLICT: 409,
    ErrorCode.IDEMPOTENCY_CONFLICT: 409,
    ErrorCode.COMMAND_OUT_OF_ORDER: 409,
    ErrorCode.COMMAND_REJECTED: 422,
    ErrorCode.SNAPSHOT_VERSION_UNSUPPORTED: 422,
    ErrorCode.MANUAL_TICK_DISABLED: 403,
    ErrorCode.SIMULATION_EXECUTION_FAILED: 500,
    ErrorCode.DATABASE_UNAVAILABLE: 503,
    ErrorCode.EVENT_BROKER_UNAVAILABLE: 503,
    ErrorCode.INTERNAL_ERROR: 500,
}


class ApiError(Exception):
    """Raised anywhere in the app; mapped to the structured error envelope."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details: dict[str, Any] = details or {}
        self.status_code = status_code or HTTP_STATUS.get(code, 500)

    def to_envelope(self, request_id: str) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details,
                "request_id": request_id,
            }
        }
