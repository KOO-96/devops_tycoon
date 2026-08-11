# First Production Image Readiness — Budget & Technical Evidence

- Owner: Ops/Program · Status: **PENDING_FIRST_PRODUCTION_IMAGE_READINESS_REVIEW**
- Base: dev `a5719a2`. Branch `verify/image-budget-evidence`. **Test/tools/docs only — no
  product runtime change; no production asset/metadata.**
- Purpose: connect each **PROPOSED** budget target (numbers of record in
  `visual-asset-budget.md`, contracts in `production-asset-budget-confirmation.md`) to a
  measurement basis + synthetic evidence, and judge FU-005…010. **No target number is
  invented or changed here; nothing is promoted to CONFIRMED** (P1 promotes nothing; and
  MEASURED→REVIEWED→CONFIRMED needs Ops+Frontend review then DevCTO sign-off).

## Honesty flags (read first)

- **GPU numbers are ESTIMATES**, computed by the validator's own formula
  `core.gpu_bytes` (RGBA8 = `w·h·4`, mip `·4/3`). WebGL/WebGL2 do not expose true VRAM,
  so these are `ESTIMATED_GPU_TEXTURE_BYTES`, **not** measured hardware VRAM.
- **Renderer is SwiftShader (software).** All browser evidence ran on
  `ANGLE … SwiftShader driver` — per FU-010 this is **NOT a hardware-GPU result**;
  hardware-GPU verification is a separate follow-up.
- **Synthetic transfer bytes are not representative.** The deterministic fixtures are
  fully-transparent PNGs that compress far smaller than real art, so their encoded size
  demonstrates the *method/basis* only — not a production transfer estimate.
- **Swap-peak allowed bound is undefined** in the canonical docs (`§2 "(to define,
  FU-008)"`) → `TARGET_DEFINITION_REQUIRED`; the lifecycle is observed, the number is not.

## Reference environment (FU-010)

| Field | Value (this run) |
|---|---|
| OS | macOS (Darwin 25.5) |
| Browser | Chromium (Playwright) |
| Renderer | `ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (LLVM 10.0.0)), SwiftShader driver)` — **SOFTWARE** |
| WebGL | WebGL2 = true |
| Frontend build | Vite dev |
| Backend | FastAPI, `storage_backend=memory` / `event_broker=memory` |
| Network / cache | localhost HTTP; cold + `cache:no-store` refetch exercised |
| AssetManager | default `RoutingAssetLoader` → `ProductionImageAssetLoader` |

**Hardware-GPU environment is NOT available here**; the above pins a *software-renderer*
reference. Load-time and true-VRAM numbers must be restated against a named hardware env
before CONFIRMED.

## Synthetic measurement assets

Deterministic transparent RGBA PNGs (`make_png`), tmp/in-memory only. Representative
sizes chosen to bracket the PROPOSED texture target (2048² recommended / 4096² hard-max):

| dim | channels | encoded PNG bytes¹ | decoded RGBA8 (est.) | mipmapped (est.) |
|---|---|---|---|---|
| 64×64 | 4 | 96 | 16,384 (0.02 MiB) | 21,845 |
| 512×512 | 4 | 1,096 | 1,048,576 (1.00 MiB) | 1,398,101 (1.33 MiB) |
| 2048×2048 | 4 | 16,375 | 16,777,216 (16.00 MiB) | 22,369,621 (21.33 MiB) |
| 4096×4096 | 4 | 65,299 | 67,108,864 (64.00 MiB) | 89,478,485 (85.33 MiB) |

¹ transparent-fill encoded size — **not representative** of real art transfer.
Pinned by `tests/asset_ops/test_image_budget_evidence.py`.

## Budget matrix (PROPOSED targets ↔ evidence)

| Metric | Proposed target | Measurement basis | Observed / Estimated | Headroom | Verdict | Evidence |
|---|---|---|---|---|---|---|
| Texture dimension | ≤2048² rec, ≤4096² hard-max | pixel dims (IHDR) | synth up to 4096² | at cap | **PASS** (enforced) | C15 |
| Decoded texture bytes | RGBA8 `w·h·4` | `core.gpu_bytes` | 2048²=16 MiB, 4096²=64 MiB | — | **PASS** (formula) | evidence test |
| Mipmapped bytes | `·4/3` per opt-in | `core.gpu_bytes(mipmap)` | 2048²=21.33 MiB, 4096²=85.33 MiB | 4096²+mip **over** resident | **PASS** (formula) | evidence test |
| Critical GPU memory | ≤32 MiB | Σ critical decoded | single ≤2048² within; 4096²=64 MiB over | — | **PASS** (enforced) | C18 |
| Resident GPU memory | ≤64 MiB | Σ resident decoded | 4096² alone = whole cap | zero at 4096² | **PASS** (enforced) | C18 |
| 4096² dimension | exception-only | dims + exception record | 64 MiB = whole resident | none | **PASS** (default DENIED) | C15 + exception |
| Swap peak | **(to define)** | old+new coexistence | lifecycle observed (A+B then cleanup) | — | **UNDEFINED** | swap-peak test |
| Initial transfer | ≤8 MiB (bundle) | HTTP download bytes (cold, post-encoding) | synth per-asset ≪ target (not representative) | — | **UNDEFINED** (real-art) | FU-009 |
| Retry / integrity-refetch transfer | (basis) | extra HTTP requests | 503→retry→200; mismatch→`no-store` refetch | — | method demonstrated | loader tests |

`PASS (enforced)` = the validator enforces the target mechanism; `PASS (formula)` = the
estimate equals the canonical formula; `UNDEFINED` = target number or representative
measurement not available.

## FU-005…010 status

| FU | Item | Status | Basis |
|---|---|---|---|
| POLICY-C-FU-005 | Deterministic generation | **COMPLETE_BY_P3A_P4_EVIDENCE** | A/B byte-stability, canonical `build_id`, drift enforcement (verify-generated), diff temp roots / order-independent — proven in P3A + P4 |
| POLICY-C-FU-006 | Mipmap budget | **COMPLETE** (formula + enforcement) | `core.gpu_bytes` mipmap flag + C18 critical/resident; VRAM itself not measured (ESTIMATE) |
| POLICY-C-FU-007 | 4096² exception | **COMPLETE** (mechanism) | C15 hard-max + DevCTO exception waiver; C18 resident sum; default **DENIED**, exception **FORMAL_APPROVAL_REQUIRED** |
| POLICY-C-FU-008 | Swap peak | **EVIDENCE_READY** (method + lifecycle) · **TARGET_DEFINITION_REQUIRED** (bound number) | version-swap A+B coexistence → cleanup, no double-destroy; canonical peak bound "to define" |
| POLICY-C-FU-009 | Transfer basis | **EVIDENCE_READY** (basis defined; method demonstrated) | HTTP-download-bytes basis defined in doc; C17 static check exists; real-art transfer + C17↔browser delta pending |
| POLICY-C-FU-010 | Reference environment | **EVIDENCE_READY** (software) · hardware-GPU **BLOCKED** | ref-env recorded (SwiftShader software); hardware-GPU run is a separate follow-up |

## Verdicts

- **Budget: `PROPOSED_TARGETS_WITH_GAPS`.** Gaps: swap-peak bound UNDEFINED; hardware-GPU
  VRAM not measured (software renderer only); real-art transfer not measured; CONFIRMED
  requires the MEASURED→REVIEWED→CONFIRMED workflow + DevCTO sign-off. **Not** promoted to
  CONFIRMED; no measurement adjusted to fit a target.
- **First Production Image Technical Readiness: `NOT_READY`.** Enforcement *mechanisms*
  are in place (deterministic generation, mipmap formula, dimension/4096² exception,
  validator C01–C26, enforced required check, real-app E2E), but readiness is blocked by
  the budget gaps above (swap-peak number, hardware-GPU, real-art transfer).
- **First Production Image Asset Gate: `CLOSED`** (unchanged). A dry-run + estimates are
  not production approval.

## Required-check impact

**No new budget enforcement is added to `asset-production-gate` in this step** (policy →
target → measurement → confirmation must complete first). A future automated budget/CI
gate is a separate follow-up (**P4-BUDGET-FU-001**), gated on CONFIRMED numbers.

## Remaining before the First Production Image Asset Gate can open

Real production asset candidate · approval · license/provenance evidence · Budget
**CONFIRMED** (incl. defined swap-peak bound, hardware-GPU VRAM evidence, real-art
transfer measurement, DevCTO sign-off) · formal First-Production-Asset-Gate review.

## Not done (constraints)

No production asset/metadata/CDN, no license approval, no `APPROVED_FOR_PRODUCTION`
production record, no atlas/P3B, no EVENT_DERIVED / Visual-PR-D, no budget SLA promotion,
no `dev→main`, no release/deploy, Gate not opened.
