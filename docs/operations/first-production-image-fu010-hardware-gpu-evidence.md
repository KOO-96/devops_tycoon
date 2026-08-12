# FU-010 — Hardware GPU Runtime Evidence (Apple Silicon / Metal) (POLICY-C-FU-010)

- Owner: Ops · Status: **POLICY-C-FU-010: MEASURED_PENDING_REVIEW**
- Scope: **evidence / test-harness / env only — no product code changed, no production asset.**
- Goal: verify **Chromium → WebGL2 → ANGLE/Metal → Apple GPU** is actually active (not
  SwiftShader), and that the real DevOps Tycoon runtime + Production Image path render on
  hardware. **VRAM is not measured** — GPU byte figures stay estimates.

## 1. Reference environment (§20)

| Field | Value |
|---|---|
| dev HEAD | `9c4f8dd` (origin/dev) |
| Mac model | MacBook Pro (`Mac16,6`) |
| Apple chip | **Apple M4 Max** (16 cores: 12P + 4E), arm64 |
| macOS | 26.5.2 (build 25F84) |
| RAM | 64 GB |
| Browser (renderer probe) | Google Chrome **151.0.7922.109** (system) |
| Browser (regression suites) | Playwright bundled Chromium **131.0.6778.33**, forced to Metal |
| WebGL version | **WebGL2** (`SUPPORTED`) |
| WebGL vendor | `Google Inc. (Apple)` |
| WebGL renderer | **`ANGLE (Apple, ANGLE Metal Renderer: Apple M4 Max, Unspecified Version)`** |
| ANGLE backend | **Metal** |
| Hardware acceleration | **ENABLED** (Apple GPU via Metal) |
| SwiftShader | **NOT used** (hardware) |
| DPR | 1 |
| viewport (headed game) | 1600×913 (also verified 1440×810, 1280×720, 1024×768) |
| frontend mode | Vite dev (`pnpm dev --port 5173`) |
| backend mode | in-memory (`uvicorn backend.app:create_app --factory --port 8000`) |
| cache state | probes `no-store`; game default |
| Pixi version | PixiJS `^8.6.6` |

## 2. Hardware acceleration — confirmed, not SwiftShader (§5 / §6 / §7)

`UNMASKED_RENDERER_WEBGL` read three independent ways, all identical:
1. standalone `canvas.getContext('webgl2')` probe (the §7 snippet),
2. the **live game canvas** at `/game/<sid>`,
3. every regression suite (asset-runtime / production-image / visual-c) stdout.

```
webgl2:   true
vendor:   Google Inc. (Apple)
renderer: ANGLE (Apple, ANGLE Metal Renderer: Apple M4 Max, Unspecified Version)
contextLost: false
```

This is a **hardware** result — SwiftShader would report `SwiftShader Device`. **None** of the
FU-010 hard-failure renderers (SwiftShader / llvmpipe / Software Rasterizer / software renderer)
were observed → **not** `BLOCKED_HARDWARE_ACCELERATION_NOT_ACTIVE`.

### chrome://gpu (§8) — limitation
System Chrome restricts `chrome://` scripting under automation: `chrome://gpu` returned an empty
document body to the automation context, so the Graphics-Feature-Status text could not be
programmatically captured. The `UNMASKED_RENDERER` (ANGLE Metal, Apple M4 Max) is the
authoritative hardware-acceleration evidence; a human can additionally confirm
`WebGL/WebGL2: Hardware accelerated` by opening `chrome://gpu` directly.

## 3. Real game rendering on hardware (§9)

Backend (memory mode, `:8000`) + Vite dev (`:5173`) up; session `POST /api/v1/game-sessions`
+ 54 nodes (26 app_server + 14 redis + 14 postgresql). Loaded `/game/<sid>` in Chrome on Metal:
- **1 canvas**, WebGL2 hardware context, **contextLost = false**.
- Pixi scene: isometric campus board with **APP / REDIS / DB** node sprites + connections.
- Left menu (Campus/Build/Connect/Deploy/Monitor/Research); right Inspector + **Nodes (54)** list;
  top HUD (TICK / REVISION / SPEED / STATE Running / CASH / trust / **WebSocket Live · Backend ok**);
  bottom SIMULATION Pause/1×/2×/4×. No black canvas, no corruption.

## 4. Browser regression on hardware (§12) — all PASS on Apple GPU

Existing specs, run through Metal (bundled Chromium `--use-gl=angle --use-angle=metal
--enable-gpu`; renderer confirmed Apple M4 Max in each):

| Suite | Result | Notes |
|---|---|---|
| `asset-runtime` | **1 passed** | fallback tiers / checksum recovery / races vs real AssetManager, WebGL2 |
| `production-image` | **1 passed** | fetch → checksum → decode → fallback via ProductionImageAssetLoader → Pixi Texture |
| `visual-c` (full app) | **5 passed** | bootstrap 1 canvas/1 game socket, 54 nodes, route ×10, 1440×810 + 1280×720 |
| `image-dryrun` | N/A on dev | harness lives on the archived P4 branch (never merged); not present on dev |

Console errors **0**, page errors **0**, WebGL errors **0**, context loss **0** across all suites.

## 5. Production Image pipeline + representative images on hardware (§10 / §11)

Representative (NON-PRODUCTION, FU-009) samples fetched over real HTTP and driven through
**fetch → WebCrypto SHA-256 → `createImageBitmap` decode → `gl.texImage2D` GPU upload** on the
Apple GPU:

| Sample | SHA-256 (prefix) | WxH | `glError` | GPU bytes (est. RGBA8) | GPU bytes (est. mip ×4/3) |
|---|---|---:|---:|---:|---:|
| raw_1 hud_dashboard | 71fb8550… | 1536×1024 | 0 | 6,291,456 | 8,388,608 |
| raw_2 network_flow | 45fadee8… | 1536×1024 | 0 | 6,291,456 | 8,388,608 |
| raw_3 fire_overload | 186dd8c3… | 1536×1024 | 0 | 6,291,456 | 8,388,608 |
| raw_4 portal_core | 4c878a87… | 1536×1024 | 0 | 6,291,456 | 8,388,608 |

All 4 uploaded to GPU textures, `glError = 0`, **contextLost = false**. SHA-256 match the FU-009
records. The full `ProductionImageAssetLoader → Pixi Texture → WebGL2` path is additionally
proven on hardware by the passing `production-image` suite (§4). These are
**NON_PRODUCTION_REPRESENTATIVE_EVIDENCE** — not registered as production assets.

## 6. Swap lifecycle on hardware (§15) — lifecycle observed, bytes estimated

Raw-GL swap observation on Metal (basis `OLD_PLUS_NEW_RESIDENT_COEXISTENCE`):

| Step | Estimated bytes |
|---|---:|
| A resident (steady) | 6,291,456 |
| A + B coexistence (**peak**) | 12,582,912 (12.0 MiB) |
| release A → B only (post-cleanup == steady(new)) | 6,291,456 |
| resident ceiling | 67,108,864 (64 MiB) |
| peak within ceiling | **yes** (12.0 MiB ≤ 64 MiB) |
| context lost ever | **false** |

Result labels: **`SWAP_LIFECYCLE_HARDWARE_OBSERVED`** + **`SWAP_PEAK_GPU_BYTES_ESTIMATED`**. The
browser does not expose real VRAM, so the peak is an **estimate** (`w·h·4`, mip `×4/3`), **not**
`VRAM_MEASURED`. **4096² exception was not applied** (§16 — `BUDGET-RUNTIME-FU-004` OPEN;
release-before-load orchestration not mechanically guaranteed); only representative
(≤ resident) textures were exercised.

## 7. VRAM honesty (§14)

- **Not** `VRAM_MEASURED`. GPU memory is `GPU_TEXTURE_BYTES_ESTIMATED` (`RGBA8 = w·h·4`; mip
  `× ~4/3`) — the existing canonical estimate, unchanged.
- The new fact recorded here is **`HARDWARE_GPU_RUNTIME_OBSERVED`**: real Apple-GPU render +
  texture upload + swap lifecycle succeeded with no GL error / no context loss.

## 8. MPS (§17)

Repository has **no PyTorch / no Python GPU compute** (`import torch` → ModuleNotFoundError; no
`torch` usage in the codebase). Therefore MPS is **N/A** to this project. `MPS_AVAILABLE` and
`WEBGL_HARDWARE_ACCELERATED` are distinct; FU-010's completion criterion is **browser hardware
GPU rendering**, which is satisfied above.

## 9. Product code / bugs (§18)

- **No product runtime code changed.** Only test harness / env / evidence.
- **Product bug:** none. One observation — under **headed system Chrome** the browser
  auto-requests `/favicon.ico`, which the dev server returns `404` for (no favicon declared in
  `index.html`). This is a **browser-chrome artifact, not a product code path**: the game code
  never requests it, there is no functional impact, and the bundled-Chromium harnesses (which do
  not request a favicon) run with 0 console errors. **Not** a `FU-010_PAUSED_FOR_PRODUCT_FIX`
  condition; noted for awareness only.

## 10. Status (§19 / §21)

- **POLICY-C-FU-010: `MEASURED_PENDING_REVIEW`.** All completion conditions met: Apple Silicon
  hardware GPU (M4 Max / Metal), **not** SwiftShader, WebGL2 hardware-accelerated, real game
  render, Production Image loader PASS, Pixi texture PASS, browser regression PASS (asset-runtime
  / production-image / visual-c), console/page/WebGL errors 0, context loss 0, reference env
  recorded.
- **FU-008:** swap **lifecycle now HARDWARE_OBSERVED**, but peak bytes remain
  `SWAP_PEAK_GPU_BYTES_ESTIMATED` → FU-008 stays `POLICY_DEFINED_PENDING_MEASUREMENT` (no real
  VRAM measurement possible in-browser).
- **Budget:** `PROPOSED_TARGETS_WITH_GAPS` (unchanged; nothing promoted to CONFIRMED).
- **First Production Image Technical Readiness:** `NOT_READY` (hardware-env item now satisfied,
  but budget not CONFIRMED, FU-009 bundle-composition pending, FU-008 peak still estimated, no
  production assets).
- **First Production Image Asset Gate:** **CLOSED** (not opened here).
