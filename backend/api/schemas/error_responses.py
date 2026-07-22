"""Reusable OpenAPI ``responses=`` maps for the common error envelope.

Declaring these on each route does two things:

1. Documents the concrete error codes a client can receive per endpoint.
2. Overrides FastAPI's default ``422 HTTPValidationError`` with the real
   ``ErrorResponse`` envelope the app actually returns (the RequestValidationError
   handler serializes VALIDATION_ERROR into this envelope).

Each HTTP status maps to a single response object; when several ``ErrorCode``s
share a status (e.g. 409 REVISION_CONFLICT / IDEMPOTENCY_CONFLICT) the codes are
enumerated in the description. The precise machine-readable code is always in
``error.code`` (typed by the ``ErrorCode`` enum in ``ErrorResponse``).
"""

from __future__ import annotations

from typing import Any

from backend.api.schemas.models import ErrorResponse


def _r(description: str) -> dict[str, Any]:
    return {"model": ErrorResponse, "description": description}


# Individual, reusable entries keyed by HTTP status.
VALIDATION = _r("VALIDATION_ERROR — malformed request (schema, strict ints, unknown command).")
NOT_FOUND = _r("SESSION_NOT_FOUND — unknown session id.")
CONFLICT_COMMAND = _r("REVISION_CONFLICT (stale expected_revision) or IDEMPOTENCY_CONFLICT.")
CONFLICT_REVISION = _r("REVISION_CONFLICT — stale expected_revision.")
COMMAND_FAULT = _r("SIMULATION_EXECUTION_FAILED or INTERNAL_ERROR.")
INTERNAL = _r("INTERNAL_ERROR — unhandled server fault.")
DB_UNAVAILABLE = _r("DATABASE_UNAVAILABLE.")
DB_OR_BROKER_UNAVAILABLE = _r("DATABASE_UNAVAILABLE or EVENT_BROKER_UNAVAILABLE.")
MANUAL_TICK_DISABLED = _r("MANUAL_TICK_DISABLED — dev-only advance endpoint is disabled.")


CREATE_SESSION_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: VALIDATION,
    500: INTERNAL,
    503: DB_UNAVAILABLE,
}

READ_SESSION_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: NOT_FOUND,
    422: VALIDATION,
    500: INTERNAL,
    503: DB_UNAVAILABLE,
}

COMMAND_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: NOT_FOUND,
    409: CONFLICT_COMMAND,
    422: VALIDATION,
    500: COMMAND_FAULT,
    503: DB_OR_BROKER_UNAVAILABLE,
}

ADVANCE_RESPONSES: dict[int | str, dict[str, Any]] = {
    403: MANUAL_TICK_DISABLED,
    404: NOT_FOUND,
    409: CONFLICT_REVISION,
    422: VALIDATION,
    500: COMMAND_FAULT,
}
