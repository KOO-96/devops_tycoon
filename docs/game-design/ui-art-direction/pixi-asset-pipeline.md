# PixiJS Asset Pipeline

- Owner: Program (spec) / Frontend (impl) · Status: Proposed

## Format & packing
- **PNG** with transparency for source sprites; **WebP** optional for large backgrounds
  (decide per-asset). Transparent backgrounds for all sprites.
- **Texture atlas / sprite sheet** per logical group (buildings, effects, characters, ui),
  with JSON atlas metadata (PixiJS `Assets`/`Spritesheet` compatible).
- **Atlas metadata:** frame rects, pivots/anchors, animation frame tags, and an
  `assetVersion` field for cache-busting.

## Logical sizing & scaling
- Author at the Confirmed logical tile (UI-D-002); render with **integer scaling** only.
- Anchor: building = bottom-center on the footprint tile anchor; effects = center.
- Footprint: declared N×N tiles per building; drives placement + selection bounds.
- Z-index: within the node layer, sort by `(col+row)` screen depth.
- Hit area: functional buildings only, set to the footprint diamond; decorative sprites get
  no hit area.
- Selection bounds: footprint diamond (fallback to sprite bounds).

## Frame naming (Proposed convention)
```
building_app_server_tier1_healthy
building_app_server_tier1_warning
building_redis_tier1_idle
building_postgresql_tier1_pool_critical
building_load_balancer_tier1_down
effect_request_packet_blue_01
effect_connection_flow_01
icon_incident_db_pool_critical
icon_nav_build
character_sre_walk_01        (Phase 2)
```
Pattern: `<category>_<kind>_<tier?>_<state|variant>_<frame?>`.

## Proposed asset paths (new; `frontend/public/` does not yet exist)
```
frontend/public/assets/game/
  atlas/          # packed sheets + json
  buildings/      # source building sprites
  effects/        # request/connection/status effects
  characters/     # decorative staff (Phase 2)
  ui/             # nav/status icons, panel chrome
  backgrounds/    # sky / ground / campus vista
```

## Lifecycle (Confirmed principles — align with current GameScene)
- **One** Pixi `Application` per GamePage (already enforced).
- Preload the MVP atlas(es) during `loadState = loading`; lazy-load Phase 2 groups.
- Reuse sprites; cache static terrain/background (render-to-texture where useful).
- Cull off-screen objects; cap concurrent animations and particles (see performance).
- Release textures / `destroy({children, texture})` on scene teardown (already implemented).
- **Fallback asset:** a neutral placeholder sprite per building kind if an atlas frame is
  missing, so a missing asset never breaks the board (log, don't crash).

## Animation frame spec (Proposed defaults — validate)
- Idle: 2–4 frames, ~4 FPS, loop.
- Selection ring: shader/tween, no frames.
- Warning pulse: ~2 FPS loop; Critical: ~6 FPS loop + slight shake.
- Request/connection flow: sprite tween along the line; rate scales with SET_SPEED.
- Build/remove, deploy/rollback: 6–10 frames, one-shot, start on command result, stop on
  completion. Down: transition to a static "down" frame + smoke loop.

## Drift / codegen note
Building visuals are data-driven off the Confirmed node kinds + health enum, so adding art
must not require Backend/contract changes. Any TypeScript client regeneration stays under
BACK-FU-008; this pipeline adds no OpenAPI surface.
