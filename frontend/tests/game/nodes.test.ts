import { describe, expect, it } from 'vitest';
import { nodeStatusText, nodeVisual, snapshotToBoardNodes } from '../../src/game/pixi/nodes';
import { makeSnapshot } from '../helpers/factories';

describe('node visuals', () => {
  it('conveys status by colour AND pattern AND label (not colour alone)', () => {
    const healthy = nodeVisual({ id: 'a', kind: 'app_server', health: 'Healthy', enabled: true });
    const down = nodeVisual({ id: 'a', kind: 'app_server', health: 'Down', enabled: true });
    expect(healthy.color).not.toBe(down.color);
    expect(healthy.pattern).not.toBe(down.pattern);
    expect(healthy.glyph).toBeTruthy();
    expect(healthy.label).toBe('APP');
  });

  it('marks disabled nodes distinctly', () => {
    const off = nodeVisual({ id: 'a', kind: 'app_server', health: 'Healthy', enabled: false });
    expect(off.label).toContain('off');
  });

  it('produces a screen-reader friendly status line', () => {
    expect(nodeStatusText({ id: 'db-1', kind: 'postgresql', health: 'Critical', enabled: true })).toBe(
      'DB db-1: Critical',
    );
  });

  it('flattens a snapshot into board nodes across all kinds', () => {
    const snapshot = makeSnapshot({
      load_balancers: { 'lb-1': { id: 'lb-1', kind: 'load_balancer', enabled: true, health: 'Healthy' } },
      databases: { 'db-1': { id: 'db-1', kind: 'postgresql', enabled: true, health: 'Warning' } },
    });
    const nodes = snapshotToBoardNodes(snapshot);
    const ids = nodes.map((n) => n.id).sort();
    expect(ids).toEqual(['app-1', 'db-1', 'lb-1']);
  });

  it('returns an empty list for a null snapshot', () => {
    expect(snapshotToBoardNodes(null)).toEqual([]);
  });

  it('defaults a missing health (e.g. load_balancer) to Healthy (no undefined)', () => {
    const snapshot = makeSnapshot({
      app_servers: {},
      // load_balancer snapshot node has no `health` field (backend to_dict omits it).
      load_balancers: { 'lb-1': { id: 'lb-1', kind: 'load_balancer', enabled: true } as never },
    });
    const nodes = snapshotToBoardNodes(snapshot);
    const lb = nodes.find((n) => n.id === 'lb-1');
    expect(lb?.health).toBe('Healthy');
  });
});
