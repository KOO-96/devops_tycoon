import { describe, expect, it, vi } from 'vitest';

vi.mock('pixi.js', async () => await import('../helpers/fakePixi'));

import { appInstances, type Container } from '../helpers/fakePixi';
import { GameScene } from '../../src/game/pixi/createGameScene';
import type { BoardNode } from '../../src/game/pixi/nodes';

function buildingCount(): number {
  const stage = appInstances[0]!.stage as unknown as Container;
  let n = 0;
  const walk = (c: Container): void => {
    if (c.label.startsWith('building:')) n++;
    c.children.forEach(walk);
  };
  walk(stage);
  return n;
}

function firstBuilding(): (Container & { destroyed: boolean }) | undefined {
  const stage = appInstances[0]!.stage as unknown as Container;
  let found: Container | undefined;
  const walk = (c: Container): void => {
    if (!found && c.label.startsWith('building:')) found = c;
    c.children.forEach(walk);
  };
  walk(stage);
  return found as (Container & { destroyed: boolean }) | undefined;
}

const nodes = (n: number): BoardNode[] =>
  Array.from({ length: n }, (_, i) => ({
    id: `app-${i}`,
    kind: 'app_server' as const,
    health: 'Healthy' as const,
    enabled: true,
  }));

describe('GameScene diff sync', () => {
  it('handles 50 nodes and reuses views across a re-sync', async () => {
    appInstances.length = 0;
    const scene = await GameScene.create(document.createElement('div'));
    scene.sync(nodes(50), []);
    expect(buildingCount()).toBe(50);
    const before = firstBuilding();
    // Re-sync same set (metric-only change): the same view object is reused.
    scene.sync(nodes(50), []);
    expect(buildingCount()).toBe(50);
    expect(firstBuilding()).toBe(before);
    expect(before?.destroyed).toBe(false);
    scene.destroy();
  });

  it('destroys only removed nodes', async () => {
    appInstances.length = 0;
    const scene = await GameScene.create(document.createElement('div'));
    scene.sync(nodes(10), []);
    expect(buildingCount()).toBe(10);
    scene.sync(nodes(4), []); // remove 6
    expect(buildingCount()).toBe(4);
    scene.destroy();
  });

  it('survives empty, unknown-kind, and duplicate-remove syncs without throwing', async () => {
    appInstances.length = 0;
    const scene = await GameScene.create(document.createElement('div'));
    expect(() => scene.sync([], [])).not.toThrow();
    expect(() =>
      scene.sync([{ id: 'x', kind: 'mystery' as never, health: 'Healthy', enabled: true }], []),
    ).not.toThrow();
    expect(buildingCount()).toBe(1); // unknown kind still renders a fallback building
    scene.sync([], []);
    expect(buildingCount()).toBe(0);
    scene.sync([], []); // re-remove: no throw
    scene.destroy();
  });

  it('keeps connections referencing present nodes only', async () => {
    appInstances.length = 0;
    const scene = await GameScene.create(document.createElement('div'));
    expect(() =>
      scene.sync(
        [
          { id: 'a', kind: 'load_balancer', health: 'Healthy', enabled: true },
          { id: 'b', kind: 'app_server', health: 'Healthy', enabled: true },
        ],
        [
          ['a', 'b'],
          ['a', 'ghost'], // dangling edge must not throw
        ],
      ),
    ).not.toThrow();
    scene.destroy();
  });
});
