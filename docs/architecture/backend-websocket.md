# Backend WebSocket

- Version: v0.1.0 · Status: Draft (for review/devcto)
- Normative contract: [contracts/websocket/game-session-v1.md](../../contracts/websocket/game-session-v1.md)

## Endpoint

`WS /ws/v1/game-sessions/{session_id}?after_cursor=<int>`

## Connect flow (subscribe-first — HIGH-2 fix)

1. verify the session exists (else send `ERROR` + close)
2. **subscribe to the broker first** and pump live events into a buffer, so no
   event published during the handshake is missed
3. replay durable events with `cursor > after_cursor` from PostgreSQL (source of
   truth), paged; track `last_delivered_cursor`
4. send a `SESSION_STATE` summary
5. one **catch-up** query (`cursor > last_delivered_cursor`) — recovers events
   committed during replay and events whose Redis publish failed
6. switch to live: forward buffered/new events, **de-duplicating by `cursor`**
   (`cursor <= last_delivered_cursor` are dropped); `HEARTBEAT` on idle

Because the subscription is active before replay and a catch-up query runs before
live mode, an event committed at any point during the handshake is delivered
exactly once (buffered-and-deduped, or recovered by catch-up).

## Message envelope

Every message: `protocol_version`, `message_type`, `session_id`, `cursor`,
`payload`. Types: `SESSION_SNAPSHOT`, `SESSION_STATE`, `DOMAIN_EVENT`,
`COMMAND_RESULT`, `ERROR`, `HEARTBEAT`.

## Delivery & dedup (BACK-FU-005)

Delivery is at-least-once. Every domain event carries a backend `event_id` and a
globally-monotonic `cursor` (per-session increasing, may have gaps — see
persistence doc); clients de-duplicate by `event_id`/`cursor` and resume with
`after_cursor`. Because PostgreSQL is the source of truth, a Redis publish failure
never loses an event — it is recoverable via replay / the events cursor API.
Publish always happens **after** the DB commit.

**Recovery limit (documented):** a Redis outage that occurs *after* the handshake
completes (steady-state live mode) can drop live messages for the duration of the
outage; those events remain durable in PostgreSQL and are recovered on reconnect
(replay from `after_cursor`) or via the events REST endpoint. A periodic DB
catch-up / outbox dispatcher for steady-state resilience is deferred (BACK-FU-004).

## Not in this PR

Inbound client command messages over WebSocket (commands go via REST in MVP);
presence/metadata; horizontal-scale fan-out is supported via the Redis broker
but multi-instance deployment/testing is deferred.
