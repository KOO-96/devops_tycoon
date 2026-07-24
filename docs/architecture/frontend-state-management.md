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

## Session load state machine (§5)

`loadState`: `idle → loading → ready`, or → `not_found` / `recoverable_error` /
`fatal_error`. `loadError` holds the `{code,message,requestId}`. Error codes map:
`SESSION_NOT_FOUND → not_found`; `DATABASE_UNAVAILABLE`/`EVENT_BROKER_UNAVAILABLE`
→ `recoverable_error` (retryable); `SNAPSHOT_VERSION_UNSUPPORTED` + any unexpected
code → `fatal_error`. Errors are never swallowed. GamePage renders a recovery
screen (never an empty board) for the three error states.

## Single bootstrap + stale-response protection (§2–§5)

All entry paths (new game, direct URL, reload, session switch, retry) go through
`controller.bootstrapSession(sessionId)`: cleanup prior session → `beginLoad`
(full store reset + `loading`) → summary → snapshot → event replay → connect
socket → `ready` → start 3s polling.

A monotonic `loadGeneration` (owned by the controller, mirrored into the store)
plus `activeSessionId` guard **every** async write: a result is applied only when
`session_id === activeSessionId AND generation === current`. Store setters add a
second guard — `setSummary`/`setSnapshot` ignore a payload whose `revision <`
current — so a late/older summary can never clobber newer state, and a same-
revision snapshot (the fuller state) is kept as a separate field from the summary.

## Snapshot is the board's source of truth (§6)

`summary` (HUD projection) and `snapshot` (full simulation state, board/NodeList)
are separate fields. After a state-changing command returns `APPLIED`/
`ALREADY_APPLIED`, the controller re-fetches the snapshot so the board reflects
backend state **without a reload**. `snapshotSyncState` (`idle|syncing|synced|
failed`) tracks this; on failure the command is NOT re-sent — a
`SnapshotSyncBanner` offers a manual "Refresh board" (§7). A snapshot update also
clears a `selectedNodeId` that no longer exists (§8). Event-delta partial updates
are a follow-up (FE-FU-005).
