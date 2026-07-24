# Frontend ↔ Backend Contract Usage

- Version: v0.1.0 · Status: Draft (for review/devcto)

The Backend contract is the source of truth: `contracts/openapi/backend-v1.json`,
`contracts/websocket/game-session-v1.md`, `contracts/commands/backend-command-v1.md`.

## REST

| call | endpoint | use |
|------|----------|-----|
| create | `POST /api/v1/game-sessions` | start; only `seed`/`users` sent (never a BalanceConfig) |
| summary | `GET /api/v1/game-sessions/{id}` | HUD; polled lightly (3s), NOT a tick scheduler |
| snapshot | `GET …/{id}/snapshot` | initial load + recovery; not per-tick |
| command | `POST …/{id}/commands` | typed discriminated union |
| events | `GET …/{id}/events` | cursor replay for recovery |

## Commands (§10–12)

14 supported commands, each a typed request `{command_id, command_type,
expected_revision?, payload}`. **`sequence` is never sent.** `command_id` is a
per-session idempotency key.

- New user intent → new `command_id`.
- Same intent retried (transport error) → **same** `command_id` + same payload.
- Payload changed → new `command_id`.
- `IDEMPOTENCY_CONFLICT` is never auto-worked-around by mutating the payload.

`expected_revision` = current store `revision`. On **REVISION_CONFLICT**: stop
(no auto-retry), read `server_revision`, refresh summary + snapshot, surface the
change, and require a new `command_id` to re-issue.

## Errors (§13)

Branch on `error.code` (12 stable codes), never on `message`. The UI shows code +
message + `request_id`; never a stack trace, SQL, or URL. Network failures map to
a stable `DATABASE_UNAVAILABLE` code.

## WebSocket (§14–17)

`WS /ws/v1/game-sessions/{id}?after_cursor=<n>`. Client-visible order: replay
`DOMAIN_EVENT`* → `SESSION_STATE` → catch-up `DOMAIN_EVENT`* → live +
`HEARTBEAT`. Handled types: SESSION_SNAPSHOT, SESSION_STATE, DOMAIN_EVENT,
COMMAND_RESULT, ERROR, HEARTBEAT.

- Unknown `message_type` → ignored (forward compatible).
- `protocol_version` mismatch → fatal connection error (no reconnect).
- Dedup by `event_id`; reconnect with `after_cursor = last_processed_cursor`.
- Reload/state loss: snapshot → REST event replay from stored cursor → live.

## BACK-FU-007 (unbounded server queue)

The client assumes the socket may drop and that a disconnect is **not** data loss
(PostgreSQL is truth; recover via replay / events API). The server may later close
slow consumers; the UI shows connection status honestly and never claims infinite
stability.

## Session bootstrap & error recovery

Every screen entry uses one `bootstrapSession` flow (summary → snapshot → event
replay → socket → ready). Load errors branch on `error.code`:
`SESSION_NOT_FOUND` → a "session not found" recovery screen (New game / back to
Start), never a blank board; `DATABASE_UNAVAILABLE`/`EVENT_BROKER_UNAVAILABLE` →
a retryable "temporarily unavailable" screen (does not claim the game is gone);
`SNAPSHOT_VERSION_UNSUPPORTED` → a distinct fatal/incompatible screen (advanced
migration UX is FE-FU-006). On any fatal bootstrap the socket, polling, and Pixi
scene are not started (or torn down), and prior session state is cleared.

After a successful state-changing command the client re-fetches the snapshot so
the board updates without a reload; a failed post-command sync surfaces a Refresh
action and never re-sends the command (same `command_id` is only for network
retries of the command itself, never for snapshot recovery).

## Authentication (§23 — Deferred)

There is **no authentication or session ownership** yet. This is a development
Foundation; the `session_id` is not a security boundary. No tokens are hard-coded.
When an auth contract lands, the API client gains a credential layer.
