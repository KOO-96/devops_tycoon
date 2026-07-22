# WebSocket Contract — game-session v1

- protocol_version: 1
- Status: Draft (Frontend + Simulation review)

## Connection

```
WS /ws/v1/game-sessions/{session_id}?after_cursor=<int, default 0>
```

- `session_id`: existing game session UUID.
- `after_cursor`: resume point; server replays events with `cursor > after_cursor`.

## Message envelope

All messages are JSON:

```json
{
  "protocol_version": 1,
  "message_type": "DOMAIN_EVENT",
  "session_id": "<uuid>",
  "cursor": 123,
  "payload": { }
}
```

Every message includes all five envelope fields. `cursor` is **always an
integer**; for messages other than `DOMAIN_EVENT` it is `0` (a placeholder, not a
valid event cursor — ignore it). Only `DOMAIN_EVENT.cursor` is meaningful for
resume/de-duplication.

## Message types

| type | when | `cursor` | payload |
|------|------|----------|---------|
| `SESSION_STATE` | after connect + replay | `0` | session summary (tick, revision, economy, incidents) |
| `SESSION_SNAPSHOT` | reserved (full snapshot on demand) | `0` | full simulation snapshot |
| `DOMAIN_EVENT` | replay + catch-up + live | event cursor | event envelope (see below) |
| `COMMAND_RESULT` | reserved (future WS command path) | `0` | command result |
| `ERROR` | failure (e.g. unknown session) | `0` | `{code, message}` |
| `HEARTBEAT` | idle keepalive (~15s) | `0` | `{}` |

## Message ordering (client-visible)

On a successful connection the server sends, in this exact order:

1. `DOMAIN_EVENT` × N — **replay** of durable events with `cursor > after_cursor`
   (may be zero).
2. `SESSION_STATE` — one summary snapshot.
3. `DOMAIN_EVENT` × M — **catch-up** of events committed during replay / not
   published (may be zero).
4. `DOMAIN_EVENT` (live) interleaved with `HEARTBEAT` (~15s idle) — steady state.

Live events with `cursor <= ` the highest already-delivered cursor are dropped
server-side (dedup). If the session does not exist, the server sends a single
`ERROR` and closes (no `SESSION_STATE`).

## Forward compatibility

- `protocol_version` is currently `1`. A client MUST check it and reject/log a
  mismatch rather than assume field shapes.
- A client MUST **ignore unknown `message_type` values** (new types may be added
  under the same `protocol_version`); do not treat them as errors.
- Inbound client messages are ignored in the MVP (used only for disconnect
  detection).

## Event envelope (`payload` of DOMAIN_EVENT)

```json
{
  "event_id": "<uuid>",
  "cursor": 123,
  "session_id": "<uuid>",
  "session_revision": 4,
  "tick": 900,
  "type": "REQUEST_FAILED",
  "target": null,
  "payload": { "reason": "DATABASE_NOT_CONNECTED", "count": 17 }
}
```

- `event_id`: backend-assigned, unique — use for de-duplication.
- `cursor`: **globally monotonic** BIGINT (increasing within a session but may
  have gaps from other sessions' events — a gap is NOT a missing event). Use the
  highest processed `cursor` as the next `after_cursor` (exclusive).
- Simulation event data is preserved verbatim in `payload`; a missing `target`
  is `null` (never inferred). User-facing prose is produced by Frontend / a future
  CTO layer, not here.

## Handshake, reconnect & de-duplication

- On connect the server subscribes to live events **before** replaying from
  PostgreSQL and runs a catch-up query, so an event committed during the
  handshake is delivered exactly once (no gap, no duplicate).
- Delivery is **at-least-once**. Reconnect with the highest processed `cursor` as
  `after_cursor`; the server replays only newer events.
- De-duplicate by `event_id` (and/or ignore `cursor <= last_seen`).
- PostgreSQL is the source of truth; the events REST endpoint
  (`GET /api/v1/game-sessions/{id}/events?after_cursor&limit`) returns the same
  ordering and identities for recovery.
- A Redis outage during steady-state live mode may drop live messages for its
  duration; recover by reconnecting (replay) or the events REST endpoint. Durable
  events are never lost (PostgreSQL is the source of truth).

## Errors

`ERROR` messages carry `{code, message}` using the same codes as the REST error
contract (e.g. `SESSION_NOT_FOUND`). The socket is closed after a fatal `ERROR`.

## Change control

Any change to this contract requires Frontend and Simulation review.
