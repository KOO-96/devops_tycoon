# Frontend Overview

- Version: v0.1.0 · Status: Draft (for review/devcto)
- Location: `frontend/` (React + TypeScript strict + Vite + PixiJS + Vitest)

MVP game client that connects to the Backend Foundation. The Backend REST/OpenAPI
and WebSocket contracts are the **source of truth**; the frontend never depends on
Backend internals or Simulation objects directly.

## Layers & boundaries

```
React UI (pages/, components/)
  │  reads stores, calls the controller
Controller (session/controller.ts)   ← the only place policy lives
  │  REST + WebSocket + stores wiring, revision/idempotency rules
API client (api/)          WebSocket client (websocket/)
  │  typed REST + errors      lifecycle + dedup + reconnect
Stores (state/, zustand)   Pixi scene (game/pixi/)
  │  UI state, event apply     isometric board, lifecycle
Contract types (api/schemas.ts, api/commandTypes.ts, api/generated/*)
```

Hard boundaries kept separate: **API client · WebSocket client · UI state · Pixi
scene · React UI · contract types**. Pure logic (coordinate math, visual mapping,
event dedup, backoff, command building) is isolated from React/Pixi so it is unit
tested without a browser.

## Screens

- `StartPage` (`/`): create a new session (seed, users) → navigate to the game.
- `GamePage` (`/game/:sessionId`): board + HUD + panels; attaches/replays on a
  cold load; opens the WebSocket.
- `NotFoundPage` (`*`).

## Tech stack

React 18, TypeScript strict (`strict`, `noUncheckedIndexedAccess`,
`exactOptionalPropertyTypes`), Vite 5, PixiJS 8, Zustand 4, react-router 6,
Vitest 2 + Testing Library. No state library beyond Zustand; Simulation logic is
never reimplemented client-side.

## Quality gates

`pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`. The Backend OpenAPI is
consumed via `pnpm generate:api` (openapi-typescript) into `src/api/generated/`;
`pnpm check:api-drift` compares generation against the committed types.
`tests/api/contract.test.ts` fails if the curated types drift from the OpenAPI
discriminator/error enums. This PR does not modify CI (infra/platform owns
BACK-FU-008 CI wiring).

## Deferred (see §5 of the task / Follow-ups)

Final art, building animations, AI-CTO chat, auth/login, payments, full campaign,
Black Friday choreography, full mobile, client tick scheduler, production deploy.
