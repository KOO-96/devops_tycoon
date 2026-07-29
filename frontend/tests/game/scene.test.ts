import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('pixi.js', async () => await import('../helpers/fakePixi'));

import { appInstances, findHandler, type Container } from '../helpers/fakePixi';
import { GameScene } from '../../src/game/pixi/createGameScene';

describe('GameScene lifecycle', () => {
  beforeEach(() => {
    appInstances.length = 0;
  });
  afterEach(() => vi.restoreAllMocks());

  it('creates a Pixi application and mounts the canvas', async () => {
    const host = document.createElement('div');
    const scene = await GameScene.create(host);
    expect(appInstances).toHaveLength(1);
    expect(appInstances[0]!.init).toHaveBeenCalled();
    expect(host.querySelector('canvas')).not.toBeNull();
    scene.destroy();
  });

  it('syncs nodes and selection without error', async () => {
    const scene = await GameScene.create(document.createElement('div'));
    scene.sync(
      [
        { id: 'lb', kind: 'load_balancer', health: 'Healthy', enabled: true },
        { id: 'app', kind: 'app_server', health: 'Warning', enabled: true },
      ],
      [['lb', 'app']],
    );
    scene.setSelection('app');
    scene.resize();
    scene.destroy();
  });

  it('reports selection through the onSelect callback', async () => {
    const onSelect = vi.fn();
    const scene = await GameScene.create(document.createElement('div'), { onSelect });
    scene.sync([{ id: 'app', kind: 'app_server', health: 'Healthy', enabled: true }], []);
    const stage = appInstances[0]!.stage as unknown as Container;
    const building = findHandler(stage, 'pointertap');
    building?.handlers['pointertap']?.[0]?.({ stopPropagation: vi.fn() });
    expect(onSelect).toHaveBeenCalledWith('app');
    scene.destroy();
  });

  it('destroy removes the resize listener and destroys the app (§26 cleanup)', async () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener');
    const scene = await GameScene.create(document.createElement('div'));
    scene.destroy();
    expect(appInstances[0]!.destroy).toHaveBeenCalled();
    expect(removeSpy).toHaveBeenCalledWith('resize', expect.any(Function));
    // Idempotent.
    scene.destroy();
    expect(appInstances[0]!.destroy).toHaveBeenCalledTimes(1);
  });

  it('drops scene ops after destroy', async () => {
    const scene = await GameScene.create(document.createElement('div'));
    scene.destroy();
    expect(() => scene.sync([], [])).not.toThrow();
  });

  it('reuses building views across syncs and removes only gone nodes', async () => {
    const scene = await GameScene.create(document.createElement('div'));
    const stage = appInstances[0]!.stage as unknown as Container;
    const countBuildings = (): number => {
      let n = 0;
      const walk = (c: Container): void => {
        if (c.label.startsWith('building:')) n++;
        c.children.forEach(walk);
      };
      walk(stage);
      return n;
    };
    scene.sync(
      [
        { id: 'a', kind: 'app_server', health: 'Healthy', enabled: true },
        { id: 'b', kind: 'redis', health: 'Healthy', enabled: true },
      ],
      [],
    );
    expect(countBuildings()).toBe(2);
    // Re-sync with one removed, one kept, one added.
    scene.sync(
      [
        { id: 'b', kind: 'redis', health: 'Warning', enabled: true },
        { id: 'c', kind: 'postgresql', health: 'Healthy', enabled: true },
      ],
      [],
    );
    expect(countBuildings()).toBe(2); // a destroyed, c created, b reused
    scene.destroy();
  });
});
