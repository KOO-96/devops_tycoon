import { describe, expect, it } from 'vitest';
import { compareDepth, depthZIndex, type DepthInput } from '../../src/game/pixi/isometric/depth';

const at = (col: number, row: number, id: string, w: 1 | 2 | 3 | 4 = 1): DepthInput => ({
  id,
  placement: { col, row, footprint: { width: w, height: w } },
});

describe('depth ordering', () => {
  it('front (higher row+col) draws later than back', () => {
    expect(depthZIndex(at(2, 2, 'x').placement)).toBeGreaterThan(depthZIndex(at(0, 0, 'x').placement));
  });

  it('large footprint sorts by its front tile', () => {
    // A 4×4 at (0,0) occupies up to (3,3); its front should outrank a 1×1 at (1,1).
    expect(depthZIndex(at(0, 0, 'big', 4).placement)).toBeGreaterThan(
      depthZIndex(at(1, 1, 'small').placement),
    );
  });

  it('equal depth breaks stably on id, never creation order', () => {
    const a = at(1, 1, 'aaa');
    const b = at(1, 1, 'bbb');
    expect(compareDepth(a, b)).toBeLessThan(0);
    expect(compareDepth(b, a)).toBeGreaterThan(0);
    // Deterministic regardless of argument order.
    expect(Math.sign(compareDepth(a, b))).toBe(-Math.sign(compareDepth(b, a)));
  });

  it('is stable across repeated sorts (no reshuffle)', () => {
    const items = [at(1, 0, 'c'), at(0, 1, 'a'), at(1, 0, 'b'), at(0, 1, 'd')];
    const first = [...items].sort(compareDepth).map((i) => i.id);
    const second = [...items].sort(compareDepth).map((i) => i.id);
    expect(second).toEqual(first);
  });
});
