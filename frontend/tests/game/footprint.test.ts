import { describe, expect, it } from 'vitest';
import {
  baseAnchor,
  centerTop,
  footprintBounds,
  intersects,
  occupiedTiles,
  selectionPolygon,
  toFootprintSide,
  type GridPlacement,
} from '../../src/game/pixi/isometric/footprint';
import { TILE_HEIGHT, TILE_WIDTH } from '../../src/game/pixi/isometric/coordinates';

const fp = (w: 1 | 2 | 3 | 4, h: 1 | 2 | 3 | 4): GridPlacement => ({
  col: 0,
  row: 0,
  footprint: { width: w, height: h },
});

describe('footprint model', () => {
  it('keeps the Confirmed 128×64 tile', () => {
    expect(TILE_WIDTH).toBe(128);
    expect(TILE_HEIGHT).toBe(64);
  });

  it('clamps footprint sides to 1..4', () => {
    expect(toFootprintSide(0)).toBe(1);
    expect(toFootprintSide(2.4)).toBe(2);
    expect(toFootprintSide(9)).toBe(4);
  });

  it('lists occupied tiles for 1×1..4×4', () => {
    expect(occupiedTiles(fp(1, 1))).toHaveLength(1);
    expect(occupiedTiles(fp(2, 2))).toHaveLength(4);
    expect(occupiedTiles(fp(3, 3))).toHaveLength(9);
    expect(occupiedTiles(fp(4, 4))).toHaveLength(16);
  });

  it('detects footprint intersection', () => {
    const a: GridPlacement = { col: 0, row: 0, footprint: { width: 2, height: 2 } };
    const b: GridPlacement = { col: 1, row: 1, footprint: { width: 2, height: 2 } };
    const c: GridPlacement = { col: 3, row: 3, footprint: { width: 1, height: 1 } };
    expect(intersects(a, b)).toBe(true);
    expect(intersects(a, c)).toBe(false);
  });

  it('anchors at the footprint bottom (grows upward)', () => {
    const small = baseAnchor(fp(1, 1));
    const big = baseAnchor(fp(4, 4));
    // Larger footprint's base sits lower on screen (greater y).
    expect(big.y).toBeGreaterThan(small.y);
  });

  it('computes screen bounds and a 4-corner selection polygon', () => {
    const b = footprintBounds(fp(2, 2));
    expect(b.maxX).toBeGreaterThan(b.minX);
    expect(b.maxY).toBeGreaterThan(b.minY);
    expect(selectionPolygon(fp(2, 2))).toHaveLength(4);
  });

  it('centerTop is within the footprint bounds', () => {
    const c = centerTop(fp(3, 3));
    const b = footprintBounds(fp(3, 3));
    expect(c.x).toBeGreaterThanOrEqual(b.minX);
    expect(c.x).toBeLessThanOrEqual(b.maxX);
  });
});
