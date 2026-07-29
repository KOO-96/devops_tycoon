/**
 * Building footprint model (1×1 … 4×4) over the 128×64 isometric grid.
 *
 * A placement has a base tile (col,row) and an N×M footprint extending toward
 * increasing col/row. All geometry is pure and unit-tested; no Pixi here.
 * `gridToScreen` is the existing, unchanged transform.
 */

import { gridToScreen, HALF_TILE_HEIGHT, type Point } from './coordinates';

export type FootprintSide = 1 | 2 | 3 | 4;

export interface TileFootprint {
  width: FootprintSide;
  height: FootprintSide;
}

export interface GridPlacement {
  col: number;
  row: number;
  footprint: TileFootprint;
}

export const DEFAULT_FOOTPRINT: TileFootprint = { width: 1, height: 1 };

/** Clamp any number to a valid 1..4 footprint side. */
export function toFootprintSide(n: number): FootprintSide {
  const v = Math.max(1, Math.min(4, Math.round(n)));
  return v as FootprintSide;
}

/** Every grid tile occupied by the placement, base at (col,row). */
export function occupiedTiles(p: GridPlacement): Point[] {
  const tiles: Point[] = [];
  for (let dc = 0; dc < p.footprint.width; dc++) {
    for (let dr = 0; dr < p.footprint.height; dr++) {
      tiles.push({ x: p.col + dc, y: p.row + dr });
    }
  }
  return tiles;
}

/** True if two placements share any tile. */
export function intersects(a: GridPlacement, b: GridPlacement): boolean {
  const aRight = a.col + a.footprint.width - 1;
  const aBottom = a.row + a.footprint.height - 1;
  const bRight = b.col + b.footprint.width - 1;
  const bBottom = b.row + b.footprint.height - 1;
  return a.col <= bRight && b.col <= aRight && a.row <= bBottom && b.row <= aBottom;
}

/**
 * Screen anchor = bottom-center of the footprint diamond, so a taller building
 * sprite grows upward without its base shifting (§12). Returns the screen point
 * of the footprint's front (max col+row) corner.
 */
export function baseAnchor(p: GridPlacement): Point {
  // Front corner tile is the max-col,max-row tile; its bottom vertex is the
  // lowest screen point of the footprint.
  const frontCol = p.col + p.footprint.width - 1;
  const frontRow = p.row + p.footprint.height - 1;
  const top = gridToScreen(frontCol, frontRow);
  return { x: top.x, y: top.y + HALF_TILE_HEIGHT };
}

/** Center of the footprint's top face (for labels / status icons). */
export function centerTop(p: GridPlacement): Point {
  const cCol = p.col + (p.footprint.width - 1) / 2;
  const cRow = p.row + (p.footprint.height - 1) / 2;
  return gridToScreen(cCol, cRow);
}

/** Screen-space AABB of the footprint diamond (min/max x/y). */
export function footprintBounds(p: GridPlacement): {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
} {
  const corners = [
    gridToScreen(p.col, p.row), // back (top)
    gridToScreen(p.col + p.footprint.width, p.row), // right
    gridToScreen(p.col, p.row + p.footprint.height), // left
    gridToScreen(p.col + p.footprint.width, p.row + p.footprint.height), // front (bottom)
  ];
  const xs = corners.map((c) => c.x);
  const ys = corners.map((c) => c.y);
  return { minX: Math.min(...xs), minY: Math.min(...ys), maxX: Math.max(...xs), maxY: Math.max(...ys) };
}

/**
 * Diamond outline (relative to the base tile's screen origin) covering the whole
 * footprint — used for the selection polygon / hit area and debug outlines.
 * Points are the four corners of the footprint diamond in screen space, relative
 * to `gridToScreen(col,row)`.
 */
export function selectionPolygon(p: GridPlacement): Point[] {
  const origin = gridToScreen(p.col, p.row);
  const rel = (col: number, row: number): Point => {
    const s = gridToScreen(col, row);
    return { x: s.x - origin.x, y: s.y - origin.y };
  };
  return [
    rel(p.col, p.row), // top
    rel(p.col + p.footprint.width, p.row), // right
    rel(p.col + p.footprint.width, p.row + p.footprint.height), // bottom
    rel(p.col, p.row + p.footprint.height), // left
  ];
}
