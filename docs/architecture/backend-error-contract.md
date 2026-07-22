# Backend Error Contract

- Version: v0.1.0 · Status: Draft (for review/devcto)

## Envelope

Every REST error returns:

```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "Game session was not found.",
    "details": {},
    "request_id": "..."
  }
}
```

`request_id` echoes/creates the `X-Request-ID` header. Internal stack traces and
DB internals are never exposed; validation `details` include only field
location/type, not raw values.

The envelope is declared in OpenAPI as `ErrorResponse` (`error.code` typed by the
`ErrorCode` enum) and is referenced by every route's `responses` for each HTTP
status it can return (404/409/422/500/503 as applicable). FastAPI's default
`HTTPValidationError` schema is overridden so the documented 422 matches the
envelope the app actually returns.

`REVISION_CONFLICT` carries recovery details:

```json
{ "server_revision": 4, "provided_revision": 3 }
```

Frontend flow: read `server_revision` → reload the summary/snapshot → retry with a
**new** `command_id`. (An idempotent retry of the *same* `command_id` returns the
stored result even when the revision is stale.)

## Codes → HTTP

| Code | HTTP | Meaning |
|------|------|---------|
| VALIDATION_ERROR | 422 | malformed input (incl. non-strict `ticks`, over-limit) |
| SESSION_NOT_FOUND | 404 | unknown session id |
| REVISION_CONFLICT | 409 | stale `expected_revision` |
| IDEMPOTENCY_CONFLICT | 409 | same `command_id`, different payload |
| COMMAND_OUT_OF_ORDER | 409 | reserved (sequences are backend-issued) |
| COMMAND_REJECTED | 422 | unknown command type at the service layer (over HTTP this is now caught earlier as VALIDATION_ERROR by the discriminated union) |
| SNAPSHOT_VERSION_UNSUPPORTED | 422 | stored snapshot version unsupported |
| MANUAL_TICK_DISABLED | 403 | dev-only advance endpoint disabled |
| SIMULATION_EXECUTION_FAILED | 500 | unexpected simulation fault |
| DATABASE_UNAVAILABLE | 503 | storage down |
| EVENT_BROKER_UNAVAILABLE | 503 | broker down |
| INTERNAL_ERROR | 500 | unhandled |

## User errors vs server faults

- Expected player-command outcomes are structured, not exceptions: a
  simulation-valid rejection returns HTTP 200 with
  `status = COMMAND_REJECTED` + `reason_code` (e.g. `server_not_found`).
- Genuine input errors and server faults use the error envelope above.
- Never hide a server fault inside a domain event; never persist partial state.
- Command identity is `(session_id, command_id)`; the DB primary key is a surrogate
  UUID, so a shared `command_id` across sessions does **not** cause a
  constraint collision. Any *unexpected* `IntegrityError` still rolls the whole
  transaction back and is mapped to a generic `INTERNAL_ERROR` (no SQL / driver
  strings, DB/Redis URLs, or file paths in the response).

## Security (deferred — NOT production-ready)

This foundation has **no authentication or session-ownership** checks: any caller
who knows a `session_id` can access it. This is explicitly not the final security
model. The dev-only advance endpoint is disabled by default. Follow-up
(owner: Backend/DevCTO): authentication and per-session authorization before any
production exposure.
