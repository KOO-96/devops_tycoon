import { describe, expect, it } from 'vitest';
import { nodeToBuildingModel } from '../../src/game/pixi/buildings/nodeBuildingAdapter';
import type { BoardNode } from '../../src/game/pixi/nodes';

const node = (over: Partial<BoardNode> = {}): BoardNode => ({
  id: 'n1',
  kind: 'app_server',
  health: 'Healthy',
  enabled: true,
  ...over,
});

describe('nodeToBuildingModel', () => {
  it('maps a known kind with its footprint and carries health/enabled verbatim', () => {
    const m = nodeToBuildingModel(node({ kind: 'postgresql', health: 'Warning' }), { col: 2, row: 1 });
    expect(m.nodeKind).toBe('postgresql');
    expect(m.footprint).toEqual({ width: 2, height: 2 });
    expect(m.health).toBe('Warning'); // not thresholded/invented
    expect(m.gridPosition).toEqual({ col: 2, row: 1 });
    expect(m.label).toContain('n1');
  });

  it('maps an unknown kind to a safe unknown building (FE-ART-001 fallback)', () => {
    const m = nodeToBuildingModel(node({ kind: 'quantum_db' as never }), { col: 0, row: 0 });
    expect(m.nodeKind).toBe('unknown');
    expect(m.footprint).toEqual({ width: 1, height: 1 });
    expect(m.label).toContain('UNKNOWN');
  });

  it('preserves node id and disabled state', () => {
    const m = nodeToBuildingModel(node({ id: 'app-9', enabled: false }), { col: 0, row: 0 });
    expect(m.nodeId).toBe('app-9');
    expect(m.enabled).toBe(false);
  });
});
