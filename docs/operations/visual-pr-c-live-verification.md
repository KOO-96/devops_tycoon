# Visual PR C — Live Verification (real browser / WebGL2)

- Owner: Ops · Status: **Ops Live-browser: VERIFIED (asset-runtime + full-app smoke)**
- Scope: real-Chromium/WebGL2 execution of the Asset Runtime fallback/checksum/race
  paths and a full-app runtime-lifecycle smoke. No product-code change; harnesses are
  test-only and excluded from the production bundle. ASSET-OPS-004 stays
  IMPLEMENTATION_PENDING (no CI added).

## Two harnesses

| Harness | Backend needed | What it proves |
|---|---|---|
| `frontend/tests/browser/asset-runtime/` (+ `asset-runtime.spec.ts`, `playwright.asset-runtime.config.ts`) | No | Fallback tiers, checksum recovery, races against the REAL AssetManager in real WebGL2 |
| `frontend/tests/browser/full-app/` (`visualPrC.spec.ts`, `playwright.visual-pr-c.config.ts`) | Yes (FastAPI + Vite) | Single canvas / single socket, 54 nodes, route×10, viewports — real app |

Both inject only the **loader response** (asset-runtime) or **Playwright-side
counters** (full-app). Neither adds a production global hook. The `ControlledAssetLoader`
is constructed via the AssetManager's public `loader` DI option.

## A. Asset-runtime harness (no backend)

```
cd frontend
pnpm install
pnpm test:browser:asset-runtime
```

Spins up its own Vite server (`tests/browser/asset-runtime/vite.config.ts`, port 5178)
and runs 10 scenarios in headless Chromium with a real WebGL2 context.

**Observed (this run):** WebGL2 = true, renderer =
`ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device …), SwiftShader driver)` — a real
(software) WebGL2 context; **not** a hardware GPU. Pixi Application initialized (WebGL).
All 10 scenarios PASS, 0 in-page/console errors:

`success · entry_fallback · category_fallback · universal_fallback · checksum_match ·
checksum_refetch_success · checksum_double_mismatch · transient_then_mismatch ·
concurrent_acquire · dispose_during_verify`

Each asserts the real runtime behavior (tier selection, `bypassCache=true` on the
single integrity refetch, corrupt-texture destroys, ≤4 attempts, shared refetch across
concurrent consumers, no result registered when disposed mid-verify).

## B. Full-app smoke (real backend)

Backend defaults to in-memory storage (needs no services). For maximum fidelity this
run used **PostgreSQL 16.14** + **Redis 7.4.9** (dedicated containers) in
`storage_backend=postgres` / `event_broker=redis` mode.

Bring-up (credentials are throwaway local values — never commit secrets):

```
# 1. services (dedicated names/ports; do not reuse unrelated containers)
docker run -d --name vc-pg -e POSTGRES_USER=devops -e POSTGRES_PASSWORD=<pw> \
  -e POSTGRES_DB=devops_tycoon -p 5433:5432 postgres:16
docker run -d --name vc-redis -p 6379:6379 redis:7

# 2. migrate + backend (in-memory mode also works: omit these env vars)
export DEVOPS_TYCOON_STORAGE_BACKEND=postgres DEVOPS_TYCOON_EVENT_BROKER=redis
export DEVOPS_TYCOON_DATABASE_URL="postgresql+asyncpg://devops:<pw>@localhost:5433/devops_tycoon"
export DEVOPS_TYCOON_REDIS_URL="redis://localhost:6379/0"
alembic upgrade head
python -m uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8000

# 3a. production preview (recommended — real prod behavior), with a proxy config
#     to forward /api and /ws to :8000 (see note), served on :4173
cd frontend && pnpm build && npx vite preview --config <proxy-preview-config>

# 3b. or dev server (note the StrictMode caveat below)
cd frontend && pnpm dev --port 5173

# 4. run the smoke against the chosen URL
VISUAL_C_BASE_URL=http://localhost:4173 pnpm test:browser:visual-c
```

> Proxy note: the production `vite.config.ts` sets `server.proxy` (dev only). To run
> the smoke against the preview build, use a throwaway `preview.proxy` config (NOT
> committed) forwarding `/api`, `/internal`, `/ws` to `:8000`, or serve `dist/` behind
> any reverse proxy. Production deployment wiring is out of scope for this PR.

**Observed (production preview, this run):** 5/5 PASS, 0 console/page/WebGL errors:
- **bootstrap** — exactly **1 canvas**, **≤1 game WebSocket**.
- **54 functional nodes** (26 app_server + 14 redis + 14 postgresql) — still **1 canvas**;
  `app-0` … `db-13` present in the accessible node list.
- **route round-trips ×10** (Start↔Game) — **1 canvas**, WebSocket **≤1** (no leak).
- **1440×810** and **1280×720** — board + node list usable, 1 canvas, no errors.

### Dev vs production socket count (important)
On the **Vite dev server** the bootstrap/round-trip socket count is **2**, because React
**StrictMode double-invokes** effects in dev (the session controller connects twice; one
is a dev-only transient). On the **production preview** build (React production mode, no
StrictMode double-invoke) the count is **1** — the true invariant. Always run the socket
assertions against the production preview.

## Not covered live (honest scope)
- **AssetManager-instance and texture counts** in the full app are not observable
  without a production global hook (forbidden). They are covered by the deterministic
  suite (203 tests incl. the StrictMode provider test) and by the asset-runtime harness.
- **Incident overflow visual** was not driven live (incidents require simulated traffic);
  the dedupe/overflow logic is covered deterministically (`incidentModel` tests) and the
  DOM panel renders the bounded model. 1280×720 board usability was confirmed live.
- SwiftShader (software WebGL2) was used — reported as such, not a hardware GPU result.

## Cleanup
```
docker rm -f vc-pg vc-redis
```

## Status
- Ops Live-browser: **VERIFIED** (asset-runtime 10/10 + full-app 5/5, real WebGL2)
- FE-ART-003 Runtime: IMPLEMENTED_PENDING_REVIEW
- ASSET-OPS-004: IMPLEMENTATION_PENDING
- Production Metadata generator: not implemented · EVENT_DERIVED: not implemented ·
  Budgets: PROPOSED TARGETS
