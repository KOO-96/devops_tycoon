import { describe, expect, it } from 'vitest';
import { nodeStatusText, snapshotToBoardNodes } from '../../src/game/pixi/nodes';
import { nodeStatusAppearance } from '../../src/game/nodeStatus';
import { makeSnapshot } from '../helpers/factories';

describe('node status text', () => {
  it('produces a screen-reader friendly status line for a reported health', () => {
    expect(nodeStatusText({ id: 'db-1', kind: 'postgresql', health: 'Critical', enabled: true })).toBe(
      'DB db-1: Critical',
    );
  });

  it('conveys status by colour AND glyph AND text (not colour alone)', () => {
    const healthy = nodeStatusAppearance({ kind: 'app_server', health: 'Healthy', enabled: true });
    const down = nodeStatusAppearance({ kind: 'app_server', health: 'Down', enabled: true });
    expect(healthy.color).not.toBe(down.color);
    expect(healthy.pattern).not.toBe(down.pattern);
    expect(healthy.glyph).toBeTruthy();
  });

  it('marks disabled nodes distinctly (not Healthy)', () => {
    const off = nodeStatusText({ id: 'a', kind: 'app_server', health: 'Healthy', enabled: false });
    expect(off).toContain('Disabled');
  });
});

describe('snapshotToBoardNodes', () => {
  it('flattens a snapshot into board nodes across all kinds', () => {
    const snapshot = makeSnapshot({
      load_balancers: { 'lb-1': { id: 'lb-1', kind: 'load_balancer', enabled: true } as never },
      databases: { 'db-1': { id: 'db-1', kind: 'postgresql', enabled: true, health: 'Warning' } },
    });
    const nodes = snapshotToBoardNodes(snapshot);
    const ids = nodes.map((n) => n.id).sort();
    expect(ids).toEqual(['app-1', 'db-1', 'lb-1']);
  });

  it('returns an empty list for a null snapshot', () => {
    expect(snapshotToBoardNodes(null)).toEqual([]);
  });

  it('carries a missing health through as undefined (never defaults to Healthy)', () => {
    const snapshot = makeSnapshot({
      app_servers: {},
      // load_balancer snapshot node has no `health` field (backend to_dict omits it).
      load_balancers: { 'lb-1': { id: 'lb-1', kind: 'load_balancer', enabled: true } as never },
    });
    const nodes = snapshotToBoardNodes(snapshot);
    const lb = nodes.find((n) => n.id === 'lb-1');
    expect(lb?.health).toBeUndefined();
    // And it renders as a neutral N/A, not Healthy.
    expect(nodeStatusText(lb!)).toBe('LB lb-1: Health N/A');
  });
});
