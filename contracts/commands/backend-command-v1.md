# Backend Command Contract

- Version: v1.0.0 · Status: Draft (for review/devcto)
- Source of truth: `contracts/openapi/backend-v1.json` (discriminated union on
  `command_type`, `oneOf` + `discriminator`). This document is the human-readable
  companion; the machine contract is the OpenAPI file.

## Request envelope

`POST /api/v1/game-sessions/{session_id}/commands`

```json
{
  "command_id": "client-idempotency-key",
  "command_type": "ADD_NODE",
  "expected_revision": 3,
  "payload": { "target": "app-2", "node_kind": "app_server" }
}
```

- `command_id` — client idempotency key, **unique per session** (free-form
  string, not necessarily a UUID). A retry with the same `(session_id,
  command_id)` and same body replays the stored result; a different body →
  `IDEMPOTENCY_CONFLICT` (409).
- `command_type` — discriminator; one of the supported values below. An unknown
  value is rejected at the API boundary with `VALIDATION_ERROR` (422).
- `expected_revision` — optional optimistic-concurrency check. If set and it does
  not equal the server revision → `REVISION_CONFLICT` (409) with
  `details = {server_revision, provided_revision}`. A stale revision on an
  **idempotent retry** still returns the stored result (idempotency precedes the
  revision check).
- `payload` — typed per `command_type`; unknown fields are rejected
  (`additionalProperties: false`).
- `sequence` is **backend-issued** and never present in a request.

## Response

`200 OK` (both applied and validly-rejected player commands):

```json
{
  "command_id": "...",
  "sequence": 1,
  "status": "APPLIED",
  "reason_code": null,
  "session_revision": 1,
  "current_tick": 0,
  "events": [ /* DomainEvent envelopes with cursor */ ],
  "state_summary": { "current_tick": 0, "cash": 1000.0, "user_trust": 0.5 }
}
```

- `status` — one of `APPLIED`, `ALREADY_APPLIED`, `DUPLICATE_COMMAND_ID`,
  `COMMAND_OUT_OF_ORDER`, `COMMAND_REJECTED`.
- `reason_code` — set when `status = COMMAND_REJECTED`; one of the values in the
  `ReasonCode` enum (see below). Branch on `status`/`reason_code`, never on
  `message`.

## Supported commands

`target` (inside `payload`) is the primary node id the command acts on. Optional
fields fall back to the simulation's defaults when omitted.

| command_type | payload fields | reject reason_code(s) |
|---|---|---|
| `ADD_NODE` | `target`*, `node_kind`* (`app_server`\|`load_balancer`\|`redis`\|`postgresql`), `weight?`, `queue_capacity?`, `mem_leak_per_tick?`, `max_connections?` | `invalid_or_duplicate_node_id`, `unknown_node_kind` |
| `REMOVE_NODE` | `target`* | `node_not_found` |
| `CONNECT` | `target`* (src), `to`* (dst) | `missing_node`, `connection_not_allowed`, `already_connected` |
| `DISCONNECT` | `target`* (src), `to`* (dst) | `not_connected` |
| `SET_LB_CONFIG` | `target`*, `algorithm?` (`round_robin`\|`weighted`\|`least_conn`), `sticky?` | `lb_not_found`, `invalid_algorithm` |
| `ENABLE_SERVER` | `target`* | `server_not_found` |
| `DISABLE_SERVER` | `target`* | `server_not_found` |
| `SET_REDIS_CONFIG` | `target`*, `ttl_ticks?`, `capacity_entries?`, `enabled?` | `cache_not_found` |
| `SET_DB_POOL` | `target`*, `max_connections?` | `db_not_found` |
| `DEPLOY` | `target`*, `version?`, `mem_leak_per_tick?` | `server_not_found` |
| `ROLLBACK` | `target`*, `to_version`* | `server_not_found`, `missing_target_version` |
| `DISABLE_FEATURE` | `target?` | (none — always accepted; MVP ops-relief hook) |
| `PAUSE` | `paused?` (default `true`) | (none) |
| `SET_SPEED` | `speed`* | `invalid_speed` |

`*` = required.

## reason_code enum (stable)

Sequence/idempotency: `duplicate_command_id`, `already_applied`,
`command_out_of_order`, `unknown_command_type`.
Domain: `invalid_or_duplicate_node_id`, `unknown_node_kind`, `node_not_found`,
`missing_node`, `connection_not_allowed`, `already_connected`, `not_connected`,
`lb_not_found`, `invalid_algorithm`, `server_not_found`, `cache_not_found`,
`db_not_found`, `missing_target_version`, `invalid_speed`.
Fallback: `rejected`.

New values are introduced via a contract version bump, not by widening to a free
string.

## Simulation mapping

The Backend `SimulationAdapter` is the sole translator: it maps this API
`command_type` (string) to `simulation.commands.CommandType`, extracts
`payload.target` into `Command.target`, passes the remaining payload through, and
runs `step(..., ticks=0)`. The API command set here is exactly the set the
Simulation Foundation implements (`simulation.commands._HANDLERS`); this table,
the adapter mapping, and the OpenAPI `discriminator.mapping` are kept in sync by
`tests/backend/api/test_openapi_contract.py`.
