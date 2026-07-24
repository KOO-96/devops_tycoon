# UI Art Direction — Master

- Owner: Program · Status: Draft (mood/world = Proposed; principles = Confirmed where tied to contracts)

## 1. Vision (Proposed)

DevOps Tycoon is a **bright, lively technology campus** where abstract DevOps concepts
become friendly, legible buildings and flows. Cute but not childish; readable at a glance;
never a horror-dark failure state. The campus is a **functional diagram in disguise**: the
real Simulation topology (nodes + connections) IS the board — not decoration.

Guiding tension: *charm must never cost clarity*. A player must always be able to tell a
Redis from a PostgreSQL, a Healthy node from a Down node, and a connected node from an
isolated one — instantly, and on a small screen.

## 2. Style pillars

| Pillar | Direction | Status |
|---|---|---|
| Medium | 2D pixel art, 2.5D isometric projection | Proposed (UI-D-001) |
| Line/shading | Thick outline or clear light/shadow break per object | Proposed |
| Palette | Limited, bright sky/greenery/panels; status colours reserved | Proposed |
| Silhouette | Each building kind has a unique silhouette | Confirmed principle |
| Status cues | Colour **+** icon **+** motion/pattern **+** text, always ≥2 non-colour cues | Confirmed principle (a11y) |
| Scaling | Integer scaling only; avoid blur / non-integer zoom | Proposed |

## 3. World mapping (Proposed names, Confirmed node kinds)

The four **Confirmed** Simulation node kinds (`load_balancer`, `app_server`, `redis`,
`postgresql`) and the four-level **Confirmed** health scale (`Healthy/Warning/Critical/
Down`, master-plan 4.9) are fixed by the implemented contract. Their in-world names/skins
are Proposed:

| Simulation node / concept | In-world building (Proposed) | Status |
|---|---|---|
| `load_balancer` | Routing Tower / Traffic Gateway | Proposed |
| `app_server` | Application Workshop / App Server Building | Proposed |
| `redis` | Cache Station (fast, temporary) | Proposed |
| `postgresql` | Data Vault / Data Center | Proposed |
| CI/CD (DEPLOY/ROLLBACK commands) | Deployment Workshop | Deferred (Phase 2) |
| Monitoring | Observability Center | Deferred (Phase 2) |
| Research | R&D Lab | Deferred (Phase 2) |
| Cloud connection | Cloud Uplink | Deferred |
| Request flow | data packets / light pulses along pipes | Proposed (Visual MVP) |

Naming must preserve technical meaning: cuteness may not blur Redis vs PostgreSQL.
Note: DEPLOY/ROLLBACK are **Confirmed commands today** (they act on an `app_server`); a
dedicated CI/CD **building** is Phase 2 — in the Visual MVP these commands animate on the
target App building, not a separate facility.

## 4. Core game principle preserved (Confirmed)

The board reflects the **real** Simulation topology. The Backend snapshot's `nodes` +
`connections` are the source of truth for the board (already implemented in the Frontend
Foundation). Requirements (Confirmed):

- One Simulation node ↔ exactly one functional on-screen object.
- App↔Cache and App↔Database connections are drawn; removing a connection removes its line.
- A Down node must not look Healthy; an Incident target is clearly identifiable.
- An unconnected node reads as physically isolated.
- Functional objects are visually distinct from decorative/facility objects.

**Functional objects** (bound to Simulation state): load balancer, app server, redis,
postgresql, real connections, incident target, request flow.
**Decorative/facility objects** (mood only, never clickable-as-function): staff characters,
benches, planters, roads, signage, decorative piping, lab backdrops, vehicles.

## 5. MVP ↔ Future split (summary; full list in visual-implementation-roadmap.md)

- **Visual MVP:** campus background, tile grid, the 4 functional buildings, connection
  lines, selection, the 4 health states, basic request flow, top HUD, alert panel, left
  nav (with correct enabled/disabled states), accessible NodeList, all load/error screens.
- **Phase 2:** CI/CD + Monitoring + Research facilities, characters, building tiers,
  build/deploy/rollback animations, environment decoration.
- **Phase 3:** campaigns, Black Friday, investor/promotion, weather/day-night, large event
  choreography, AI-CTO character + chat UI.

Future features must **not** appear as working controls in the MVP screen (no live Level,
Score, campaign gauge, investor rank, Black Friday meter — Future Slots only or hidden).

## 6. Honesty & boundaries (Confirmed)

- Frontend never asserts incident **causes**; it shows backend-provided incident
  `type/target/phase` verbatim.
- No AI-CTO persona / LLM chat shown as implemented.
- No unconfirmed reward/trust thresholds or promotion numbers displayed.
- The 3s summary poll is not presented as game-time progression; the client computes no
  ticks (Backend auto-tick scheduler is Deferred — see backend docs).
- Error/alert UI is visually distinct from in-game incidents.

## 7. Open decisions

All locking decisions are in [decisions-required.md](decisions-required.md) (UI-D-001…015).
The single most important is **UI-D-001** (final visual genre), which is gated on viewing
the actual reference image (UI-D-015).
