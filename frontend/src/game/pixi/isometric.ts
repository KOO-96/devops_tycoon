/** Isometric grid <-> screen coordinate transforms (§18). Pure & tested. */

export interface TileSize {
  width: number; // full tile width in px
  height: number; // full tile height in px (typically width/2)
}

export interface Point {
  x: number;
  y: number;
}

export const DEFAULT_TILE: TileSize = { width: 128, height: 64 };

/** Grid cell (col,row) -> screen point (origin at 0,0; caller adds camera/offset). */
export function gridToScreen(col: number, row: number, tile: TileSize = DEFAULT_TILE): Point {
  return {
    x: (col - row) * (tile.width / 2),
    y: (col + row) * (tile.height / 2),
  };
}

/** Screen point -> nearest grid cell (inverse of gridToScreen, rounded). */
export function screenToGrid(x: number, y: number, tile: TileSize = DEFAULT_TILE): Point {
  const halfW = tile.width / 2;
  const halfH = tile.height / 2;
  const col = (x / halfW + y / halfH) / 2;
  const row = (y / halfH - x / halfW) / 2;
  return { x: Math.round(col), y: Math.round(row) };
}

/**
 * Deterministic auto-layout: place nodes on a grid in stable insertion order so a
 * given set of ids always maps to the same cells (no random jitter — §4/§26).
 */
export function layoutGrid(ids: string[], columns = 4): Map<string, Point> {
  const out = new Map<string, Point>();
  ids.forEach((id, i) => {
    out.set(id, { x: i % columns, y: Math.floor(i / columns) });
  });
  return out;
}
