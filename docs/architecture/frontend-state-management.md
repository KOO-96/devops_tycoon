# Frontend State Management

- Version: v0.1.0 · Status: Draft (for review/devcto)

Two Zustand stores keep Backend-derived data separate from UI-only state; the
Backend snapshot is treated as **read-only** and never mutated in place.

## `gameSessionStore`

| field | meaning |
|-------|---------|
| `sessionId` | current session |
| `summary` | Backend `SessionSummary` (HUD source) |
| `snapshot` | Simulation snapshot (board source, read-only) |
| `revision` | monotonic session revision (never moves backwards) |
| `currentTick` | latest tick seen |
| `stateVersion` | `simulation_state_version` (distinct from revision/tick) |
| `selectedNodeId` | UI selection |
| `events` | bounded display log (cap 200) |
| `lastProcessedCursor` | replay/dedup watermark |
| `pending` | in-flight commands keyed by UI action |
| `lastError` | last error `{code, message, requestId}` |
| `_recentEventIds` | bounded dedup set (cap 4096) |

`revision`, `current_tick`, and `state_version` are **never conflated**. Summary
refresh and event application only advance them via `Math.max`, so out-of-order
arrivals never roll the UI backwards.

### Event application (dedup)

`applyEvent` de-duplicates by `event_id` (bounded set), ignores an
already-delivered cursor (`cursor <= lastProcessedCursor`), then advances
`lastProcessedCursor`, `currentTick`, `revision`, and appends to the bounded log.
Cursors are global and may have gaps within a session — a gap is not a lost event.

## `connectionStore`

`socketStatus` (idle/connecting/connected/reconnecting/disconnected/failed),
`backendStatus` (unknown/ok/unreachable), `protocolError`. Drives the connection
banner independently of game data.

## Pending commands (§22)

A UI action has a stable `key`. `beginPending`/`clearPending` gate concurrent
clicks: while a key is in flight, repeat clicks are ignored. The controller keeps
an intent registry (`key → {commandId, payloadKey}`) so an identical retry reuses
the `command_id` and a changed payload gets a new one.
