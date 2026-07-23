import { describe, expect, it } from 'vitest';
import { gridToScreen, layoutGrid, screenToGrid } from '../../src/game/pixi/isometric';

describe('isometric transforms', () => {
  it('maps grid to screen and back (round-trip)', () => {
    for (const [col, row] of [[0, 0], [1, 0], [0, 1], [3, 2], [5, 5]] as Array<[number, number]>) {
      const screen = gridToScreen(col, row);
      const back = screenToGrid(screen.x, screen.y);
      expect(back).toEqual({ x: col, y: row });
    }
  });

  it('origin maps to (0,0)', () => {
    expect(gridToScreen(0, 0)).toEqual({ x: 0, y: 0 });
  });

  it('lays out ids deterministically on a grid', () => {
    const layout = layoutGrid(['a', 'b', 'c', 'd', 'e'], 4);
    expect(layout.get('a')).toEqual({ x: 0, y: 0 });
    expect(layout.get('d')).toEqual({ x: 3, y: 0 });
    expect(layout.get('e')).toEqual({ x: 0, y: 1 });
    // Same input -> same output (no jitter).
    expect(layoutGrid(['a', 'b', 'c', 'd', 'e'], 4).get('e')).toEqual({ x: 0, y: 1 });
  });
});
