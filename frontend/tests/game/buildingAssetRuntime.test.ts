import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('pixi.js', async () => await import('../helpers/fakePixi'));

import { appInstances, Sprite, Text, type Container } from '../helpers/fakePixi';
import { GameScene } from '../../src/game/pixi/createGameScene';
import { AssetManager } from '../../src/game/pixi/assets/AssetManager';
import { NODE_BUILDING_ASSET_ID } from '../../src/game/pixi/assets/generatedBuildingAsset';
import type { BoardNode } from '../../src/game/pixi/nodes';
import type { IncidentSummary } from '../../src/api/schemas';

const backoffOnly = (ms: number): Promise<void> =>
  ms >= 1000 ? new Promise<void>(() => {}) : Promise.resolve();

const flush = (): Promise<void> => new Promise((r) => setTimeout(r, 0));

function findBuilding(root: Container, nodeId: string): Container | undefined {
  if (root.label === `building:${nodeId}`) return root;
  for (const c of root.children) {
    const found = findBuilding(c, nodeId);
    if (found) return found;
  }
  return undefined;
}
function spriteIn(container: Container): Sprite | undefined {
  return container.children.find((c): c is Sprite => c instanceof Sprite);
}
function labelText(container: Container): string {
  const t = container.children.find((c): c is Text => c instanceof Text);
  return t?.text ?? '';
}

const managers: AssetManager[] = [];
function makeManager(): AssetManager {
  const m = new AssetManager({ sleep: backoffOnly });
  managers.push(m);
  return m;
}

describe('functional building ↔ asset runtime', () => {
  beforeEach(() => {
    appInstances.length = 0;
  });
  afterEach(async () => {
    while (managers.length) await managers.pop()!.disposeAll();
    vi.restoreAllMocks();
  });

  it('acquires the kind development texture and attaches a Sprite', async () => {
    const assets = makeManager();
    const scene = await GameScene.create(document.createElement('div'), { assets });
    scene.sync([{ id: 'r1', kind: 'redis', health: 'Healthy', enabled: true }], []);
    await flush();
    const stage = appInstances[0]!.stage as unknown as Container;
    const building = findBuilding(stage, 'r1')!;
    expect(spriteIn(building)).toBeDefined();
    expect(assets.refCountOf(NODE_BUILDING_ASSET_ID.redis)).toBe(1);
    scene.destroy();
  });

  it('releases the asset handle when a node is removed', async () => {
    const assets = makeManager();
    const scene = await GameScene.create(document.createElement('div'), { assets });
    scene.sync([{ id: 'r1', kind: 'redis', health: 'Healthy', enabled: true }], []);
    await flush();
    expect(assets.refCountOf(NODE_BUILDING_ASSET_ID.redis)).toBe(1);
    scene.sync([], []); // remove r1
    await flush();
    expect(assets.refCountOf(NODE_BUILDING_ASSET_ID.redis)).toBe(0);
    scene.destroy();
  });

  it('an unknown kind still renders (falls back), never crashing', async () => {
    const assets = makeManager();
    const scene = await GameScene.create(document.createElement('div'), { assets });
    const node = { id: 'x1', kind: 'quantum_db', enabled: true } as unknown as BoardNode;
    expect(() => scene.sync([node], [])).not.toThrow();
    await flush();
    const stage = appInstances[0]!.stage as unknown as Container;
    expect(findBuilding(stage, 'x1')).toBeDefined();
    scene.destroy();
  });

  it('shows an incident marker on the targeted node, separate from health', async () => {
    const assets = makeManager();
    const scene = await GameScene.create(document.createElement('div'), { assets });
    scene.sync(
      [
        { id: 'lb1', kind: 'load_balancer', enabled: true },
        { id: 'app1', kind: 'app_server', health: 'Healthy', enabled: true },
      ],
      [],
    );
    const incidents: IncidentSummary[] = [{ type: 'LB_IMBALANCE', target: 'lb1', phase: 'ACTIVE' }];
    scene.setIncidents(incidents);
    await flush();
    const stage = appInstances[0]!.stage as unknown as Container;
    // The LB carries an incident tag; the healthy app does not.
    expect(labelText(findBuilding(stage, 'lb1')!)).toContain('⚑');
    expect(labelText(findBuilding(stage, 'app1')!)).not.toContain('⚑');
    scene.destroy();
  });

  it('does NOT dispose an injected manager on scene destroy; texture survives', async () => {
    const assets = makeManager();
    const disposeSpy = vi.spyOn(assets, 'disposeAll');
    const scene = await GameScene.create(document.createElement('div'), { assets });
    scene.sync([{ id: 'db1', kind: 'postgresql', health: 'Healthy', enabled: true }], []);
    await flush();
    scene.destroy();
    expect(disposeSpy).not.toHaveBeenCalled();
    // The shared manager is still usable and its textures intact after scene destroy.
    const h = await assets.acquire(NODE_BUILDING_ASSET_ID.postgresql);
    expect(h.texture).not.toBeNull();
    h.release();
  });

  it('two scenes share one injected manager and one texture per kind', async () => {
    const assets = makeManager();
    const s1 = await GameScene.create(document.createElement('div'), { assets });
    const s2 = await GameScene.create(document.createElement('div'), { assets });
    s1.sync([{ id: 'a', kind: 'app_server', health: 'Healthy', enabled: true }], []);
    s2.sync([{ id: 'b', kind: 'app_server', health: 'Warning', enabled: true }], []);
    await flush();
    // Both scenes hold a ref to the same shared app_server texture.
    expect(assets.refCountOf(NODE_BUILDING_ASSET_ID.app_server)).toBe(2);
    s1.destroy();
    s2.destroy();
  });
});
