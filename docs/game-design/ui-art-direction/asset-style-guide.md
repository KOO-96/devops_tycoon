# Asset Style Guide

- Owner: Program · Status: genre + font-role policy **Confirmed** (UI-D-001/002/007); exact
  hex values and specific font files remain Proposed.

## Rendering model (Confirmed — Illustrated Pixel Hybrid)

- **Buildings + environment + effects:** pixel-styled **illustration** — pixel outline and
  texture, more detailed than classic low-res dots. Authored at a **64×32 source module**,
  shown at the **128×64** logical tile via **2× integer scaling**, nearest-neighbor filtering.
- **UI panels + body text:** crisp, normal (non-pixel) UI — not constrained to coarse dots.
- Never force every element to low-res dots; keep pixel texture/outline + integer scaling on
  the art layers only.

## Functional building catalog

Each building needs a base silhouette + the state variants in
[ui-state-matrix.md](ui-state-matrix.md). Art is authored to the Confirmed tile from
UI-D-002.

### Routing Tower (`load_balancer`)
- Visual: tall tower with fan-out arms/gates; readable connection direction; traffic-flow
  animation. States: Healthy · Imbalanced · No-Healthy-Server · Down.

### Application Workshop (`app_server`)
- Visual: small service workshop/office; distinguishable in multiples; shows an App
  number/name. States: Healthy · CPU Warning · CPU Critical · Memory Warning · Deploying ·
  Disabled · Down.

### Cache Station (`redis`)
- Visual: fast, compact cache depot; distinct silhouette from the Data Vault; motif of
  speed / temporary storage. States: Healthy · Cache-Miss Warning · Capacity Warning ·
  Eviction · Disabled · Down.

### Data Vault (`postgresql`)
- Visual: large data vault / data center; can express connection-pool and query load.
  States: Healthy · Pool Warning · Pool Critical · CPU Warning · Down.

## Colour palette (Proposed hex — to confirm in UI-D-001)

| Role | Proposed | Notes |
|---|---|---|
| Sky | `#8FD3FF` | bright blue backdrop |
| Ground | `#6FBF73` | mid-value green |
| Panel | `#EAF2FB` | blue-white UI surfaces |
| Outline | `#2C3A47` | dark blue-grey object outline |
| Healthy | `#2ECC71` | reserved for status only |
| Warning | `#F1C40F` | |
| Critical | `#E74C3C` | |
| Down | `#7F8C8D` (or desaturated purple `#6C5B7B`) | |
| Deploying | `#4AA3FF` | |
| Selected | `#00D1D1` (cyan) | selection ring |
| Connection | per-kind/state pattern | not colour-only |

Status colours are **reserved** — do not reuse Healthy-green for generic UI chrome, so
state reads cleanly. The current Foundation already uses a compatible status palette
(`styles.css`); exact hex values remain Proposed and are confirmed during roadmap PR A.

## Typography (roles Confirmed — UI-D-007; specific fonts Proposed)

| Role | Direction | Status |
|---|---|---|
| Logo / large signage / short numeric labels | display **pixel font** | Confirmed |
| Korean body + HUD text | **legible Sans** (non-pixel) | Confirmed |
| Node IDs / technical info | **monospace** | Confirmed |
| Panel headings | medium-weight legible sans | Confirmed |

Do not use a decorative pixel font for long body or CJK text. A font stack must render
**both Korean and English** (the UI already mixes both). Do **not** commit font files —
document candidates + license review only (specific file selection is the remaining
Proposed part of UI-D-007).

## Icons (Proposed)

- Legible at 16 / 24 / 32 px; distinguishable in monochrome; always paired with a text
  label; never copied from the reference. One icon per left-nav item and per status.

## Character roster (decorative, Phase 2 — Proposed)

Developer · QA · SRE · Data Engineer · Platform Engineer · Researcher. Animations:
walk · type · server-check · deploy · acknowledge-alert · rest. Characters are **not**
Simulation nodes and never assert incident cause or act as an AI CTO (Confirmed boundary).
Whether any characters appear in the MVP = **UI-D-006** (recommended: Deferred to Phase 2).

## Animation specs (Proposed; frames/FPS to validate)

MVP-priority: node idle, selection, healthy activity, warning pulse, critical alert, down,
request flow, connection flow, build/remove, deploy/rollback, cache hit/miss, DB pool
pressure. For each define: frame count, FPS, loop?, start trigger, stop condition
(Proposed values in pixi-asset-pipeline.md). Deferred: complex character behaviour,
weather, day/night, large event choreography, Black Friday crowds, AI-CTO character.
Respect a Reduced-Motion setting (accessibility) — see UI-D-012.
