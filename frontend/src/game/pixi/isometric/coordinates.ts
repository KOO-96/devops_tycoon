/**
 * Isometric coordinate constants + re-exports (UI-D-002: logical tile 128×64).
 *
 * The coordinate transforms themselves live in the existing, tested
 * `../isometric.ts` and are NOT changed by PR B. This module only exposes named
 * TILE_WIDTH / TILE_HEIGHT constants and re-exports the transforms so the new
 * building/footprint/depth code has one import surface.
 */

import { DEFAULT_TILE, gridToScreen, screenToGrid, type Point } from '../isometric';

export const TILE_WIDTH = DEFAULT_TILE.width; // 128 (Confirmed, UI-D-002)
export const TILE_HEIGHT = DEFAULT_TILE.height; // 64 (Confirmed, UI-D-002)
export const HALF_TILE_WIDTH = TILE_WIDTH / 2;
export const HALF_TILE_HEIGHT = TILE_HEIGHT / 2;

export { DEFAULT_TILE, gridToScreen, screenToGrid };
export type { Point };
