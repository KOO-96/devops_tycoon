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

## Message types

| type | when | payload |
|------|------|---------|
| `SESSION_STATE` | after connect + replay | session summary (tick, revision, economy, incidents) |
| `SESSION_SNAPSHOT` | reserved (full snapshot on demand) | full simulation snapshot |
| `DOMAIN_EVENT` | replay + live | event envelope (see below) |
| `COMMAND_RESULT` | reserved (future WS command path) | command result |
| `ERROR` | failure (e.g. unknown session) | `{code, message}` |
| `HEARTBEAT` | idle keepalive (~15s) | `{}` |

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
