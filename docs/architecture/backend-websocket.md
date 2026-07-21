# Backend WebSocket

- Version: v0.1.0 · Status: Draft (for review/devcto)
- Normative contract: [contracts/websocket/game-session-v1.md](../../contracts/websocket/game-session-v1.md)

## Endpoint

`WS /ws/v1/game-sessions/{session_id}?after_cursor=<int>`

## Connect flow

1. verify the session exists (else send `ERROR` + close)
2. replay durable events with `cursor > after_cursor` from PostgreSQL (source of
   truth), paged
3. send a `SESSION_STATE` summary
4. stream live `DOMAIN_EVENT` messages from the broker; emit `HEARTBEAT` on idle

## Message envelope

Every message: `protocol_version`, `message_type`, `session_id`, `cursor`,
`payload`. Types: `SESSION_SNAPSHOT`, `SESSION_STATE`, `DOMAIN_EVENT`,
`COMMAND_RESULT`, `ERROR`, `HEARTBEAT`.

## Delivery & dedup (BACK-FU-005)

Delivery is at-least-once. Every domain event carries a backend `event_id` and a
monotonic `cursor`; clients de-duplicate by `event_id` and resume with
`after_cursor`. Because PostgreSQL is the source of truth, a Redis publish
failure never loses an event — it is recoverable via replay / the events cursor
API. Publish always happens **after** the DB commit.

## Not in this PR

Inbound client command messages over WebSocket (commands go via REST in MVP);
presence/metadata; horizontal-scale fan-out is supported via the Redis broker
but multi-instance deployment/testing is deferred.
