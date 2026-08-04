# Visual PR C — Policy Gates Index (DevCTO Integration)

- Owner: Program (index) · Status: **DevCTO: APPROVED_WITH_FOLLOW_UP · Visual PR C: COMPLETE_IN_DEV**
- Visual PR C runtime merged to `dev` (PR #21 → review/devcto, PR #22 → dev). Runtime
  implemented + Ops live-browser VERIFIED. First-production-asset and EVENT_DERIVED
  gates remain open (see below); numeric budgets remain Proposed.
- Purpose: single index of the Visual PR C prerequisite policies, their approval
  status, and the follow-up/gate schedule. This file **links** to the authoritative
  detail docs and does not restate policy bodies.

## Authoritative policy documents

| Policy | Document | Status |
|---|---|---|
| FE-ART-002 — Visual State Data Source Matrix | [`state-data-source-matrix.md`](./state-data-source-matrix.md) | Policy: **APPROVED_WITH_FOLLOW_UP** · Runtime impl: **IMPLEMENTED_IN_DEV** |
| FE-ART-003 — Shared Texture Lifecycle | [`../../architecture/frontend-shared-texture-lifecycle.md`](../../architecture/frontend-shared-texture-lifecycle.md) · impl [`../../architecture/frontend-asset-runtime.md`](../../architecture/frontend-asset-runtime.md) | Policy: **APPROVED_WITH_FOLLOW_UP** · Runtime impl: **IMPLEMENTED_IN_DEV** (Visual PR C) |
| ASSET-OPS-001 — Asset Metadata Schema | [`../../operations/visual-asset-metadata-schema.md`](../../operations/visual-asset-metadata-schema.md) | Policy: **APPROVED_WITH_FOLLOW_UP** · Validator/CI: PENDING |
| ASSET-OPS-002 — Asset Budget | [`../../operations/visual-asset-budget.md`](../../operations/visual-asset-budget.md) | Budget baseline: **APPROVED_WITH_FOLLOW_UP** · Numbers: **PROPOSED TARGETS** |
| Asset Manifest Operational Baseline | [`../../operations/visual-asset-manifest-policy.md`](../../operations/visual-asset-manifest-policy.md) | Policy: **APPROVED_WITH_FOLLOW_UP** · Runtime impl: **IMPLEMENTED_IN_DEV** |
| ASSET-OPS-004 — Manifest CI | (in manifest policy) · P1 contract [`../../operations/asset-ops-004-contract-matrix.md`](../../operations/asset-ops-004-contract-matrix.md) | **POLICY_DEFINED_IMPLEMENTATION_PENDING** (before first production asset) |

Parallel reviews: Backend Contract / Frontend Architecture / Ops / Program / DevCTO
= **APPROVED_WITH_FOLLOW_UP**. Cross-policy blocking issues: **NONE**.

## Follow-ups

| ID | Title | Due |
|---|---|---|
| POLICY-C-FU-001 | Formal Client Runtime source classes (CLIENT_LOCAL / CLIENT_CONNECTION / CLIENT_SYNC / ASSET_RUNTIME) | **IMPLEMENTED (PR C)** — `src/game/visualSource.ts` |
| POLICY-C-FU-002 | Event-derived visual lifecycle (start/duration/clear/replay/dedupe/late/priority/session/reduced-motion) | Before any EVENT_DERIVED effect (PR C/D) — NOT in this PR |
| POLICY-C-FU-003 | Incident overlay stacking & dedupe (same type+target, phase handling, max shown, overflow, health-badge separation) | **IMPLEMENTED (PR C)** — `src/game/incidentModel.ts` |
| POLICY-C-FU-004 | Asset retry semantics (initial + ≤2 retries = 3 max; 8s per attempt; shared per key; no retry on 4xx/schema/license) | **IMPLEMENTED (PR C)** — `src/game/pixi/assets/retry.ts` |
| POLICY-C-FU-005 | Deterministic Metadata→Manifest generation (single tool; no manual double-entry) | **POLICY_DEFINED_IMPLEMENTATION_PENDING** (P1) — before ASSET-OPS-004 & first production asset |
| POLICY-C-FU-006 | Mipmap budget enforcement (32 MiB assumes no mipmaps; opt-in recomputes) | **POLICY_DEFINED_IMPLEMENTATION_PENDING** (P1) — before first production asset |
| POLICY-C-FU-007 | Oversized (4096²) texture exception accounting vs 64 MiB resident | **POLICY_DEFINED_IMPLEMENTATION_PENDING** (P1) — before first production asset |
| POLICY-C-FU-008 | Manifest swap-peak budget (steady-state vs swap peak measured separately) | **POLICY_DEFINED_IMPLEMENTATION_PENDING** (P1) — before first production asset |
| POLICY-C-FU-009 | Critical bundle transfer measurement basis (download bytes, cold cache, format/compression recorded) | **POLICY_DEFINED_IMPLEMENTATION_PENDING** (P1) — before first production asset |
| POLICY-C-FU-010 | Asset load reference environment (browser/OS/CPU/GPU/network; start=manifest request, end=Ready incl. decode+upload) | **POLICY_DEFINED_IMPLEMENTATION_PENDING** (P1) — before first production asset |

FE-ART-003 implementation follow-ups — **IMPLEMENTED in Visual PR C**
(`frontend-asset-runtime.md`): FU-001 App-scope AssetManager hoist · FU-002 Asset
Handle + refCount + versioned cache · FU-003 HMR/test reset · FU-004 concurrent-load /
dispose-race handling. Pending review; PR C **Completion Gate** still requires the
implementation verification listed below.

Review-round-2 fixes (REQUEST_CHANGES → addressed): **three-tier fallback**
(Entry → **Category** → Universal, depth ≤ 3, cycle-guarded) and **checksum
verification with a single bounded integrity refetch** (≤ 4 total attempts) are now
implemented, plus a production fail-fast on an uninjected AssetManager and a
StrictMode provider test.

Round-3 Ops enablement: **live-browser verification is VERIFIED** — test-only
harnesses run the fallback/checksum/race paths (10/10) and a full-app lifecycle smoke
(5/5) in real Chromium/WebGL2 (SwiftShader), backend on PostgreSQL 16.14 + Redis 7.4.9.
See [`../../operations/visual-pr-c-live-verification.md`](../../operations/visual-pr-c-live-verification.md).
Harnesses are excluded from the production bundle; ASSET-OPS-004 stays
IMPLEMENTATION_PENDING (no CI added).

Round-4 socket re-verify: the earlier "2 dev game sockets" REQUEST_CHANGES was a
**measurement artifact** — the instrumentation counted Vite's dev HMR socket. Measured
by `readyState`/URL, the **game socket is 1 in both dev and preview**. The counter now
filters to the game path. A genuine (narrow) teardown-before-connect orphan-socket race
was found and fixed in `GameSessionController` (generation-safe teardown + guarded
connect/handlers), covered by `tests/session/controllerLifecycle.test.ts`.

## Gates

**PR C Start Gate** — open once these three policy PRs reach `dev`:
FE-ART-002, FE-ART-003, ASSET-OPS-001/002 + Manifest Baseline policy-approved and on
dev; DevCTO cross-policy approval recorded; follow-up due-dates classified below.

Required inside PR C (start-gate items):
POLICY-C-FU-001, -003, -004 and FE-ART-003-FU-001…004.

**Before EVENT_DERIVED effects:** POLICY-C-FU-002.

**PR C Completion Gate** — policy approval does **not** equal implementation done;
completion requires verified AssetManager hoist, Asset Handle/versioned cache,
manifest replacement + stale cleanup, HMR/test reset, load/dispose-race handling,
formal client source classes, incident overlay stacking/dedupe, and the exact retry
state machine.

**First Production Asset Gate:** POLICY-C-FU-005…010 and ASSET-OPS-004 CI. **CLOSED.**
Definition + checklist: [`../../operations/first-production-asset-gate.md`](../../operations/first-production-asset-gate.md).

## Asset Production Enablement (post-PR-C)

P1 (policy baseline, **POLICY_DEFINED_PENDING_DEVCTO_REVIEW**) defines the production-asset
governance: canonical metadata, approval states, license/provenance, deterministic
Metadata→Manifest generation, the ASSET-OPS-004 contract matrix, budget confirmation, and
the First Production Asset Gate. Canonical docs under `docs/operations/`:
`production-asset-metadata-policy.md` · `production-asset-approval-workflow.md` ·
`asset-ops-004-contract-matrix.md` · `production-asset-budget-confirmation.md` ·
`first-production-asset-gate.md`. Implementation follows as P2 (infra validator + required
CI check) · P3 (frontend deterministic generator) · P4 (end-to-end dry-run). No assets,
no CI, no budget confirmation in P1.

## Confirmed contract facts (basis)

Health = Healthy/Warning/Critical/Down · IncidentType = 8 · DomainEventType = 20 ·
reason_code = 18 · IncidentPhase = WARNING/ACTIVE/RECOVERING/RECOVERED · load_balancer
has no `health`; app_server/redis/postgresql do · no separate severity enum · raw
domain events arrive via WS/events API, not the snapshot · PixiJS resolved 8.19.0.
