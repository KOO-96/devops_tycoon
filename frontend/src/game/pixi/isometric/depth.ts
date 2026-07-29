/**
 * Stable depth ordering for the building layer (§13).
 *
 * Primary key is the footprint's FRONT tile `(row+col)` so nearer buildings draw
 * over farther ones (large footprints included). Ties break on screenY then a
 * stable id — never on creation order — so a snapshot re-sync never reshuffles
 * equal-depth buildings.
 */

import { gridToScreen } from './coordinates';
import type { GridPlacement } from './footprint';

export interface DepthInput {
  placement: GridPlacement;
  id: string;
}

/** zIndex for Pixi `sortableChildren`: larger = drawn later (in front). */
export function depthZIndex(p: GridPlacement): number {
  const frontCol = p.col + p.footprint.width - 1;
  const frontRow = p.row + p.footprint.height - 1;
  // Scale by 1000 so screenY tiebreak (below) can nudge within the same cell.
  return (frontCol + frontRow) * 1000 + Math.round(gridToScreen(frontCol, frontRow).y);
}

/** Deterministic comparator (stable for equal depth via id). */
export function compareDepth(a: DepthInput, b: DepthInput): number {
  const za = depthZIndex(a.placement);
  const zb = depthZIndex(b.placement);
  if (za !== zb) return za - zb;
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
}
