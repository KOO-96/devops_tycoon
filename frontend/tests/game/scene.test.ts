import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Mock Pixi so no real WebGL/canvas is needed. Everything the mock factory
// references must be created inside vi.hoisted (the factory is hoisted).
const h = vi.hoisted(() => {
  class FakeContainer {
    children: FakeContainer[] = [];
    position = { set: vi.fn(), x: 0, y: 0 };
    eventMode = '';
    cursor = '';
    hitArea: unknown = null;
    handlers: Record<string, Array<(e: unknown) => void>> = {};
    addChild<T extends FakeContainer>(c: T): T {
      this.children.push(c);
      return c;
    }
    removeChildren(): FakeContainer[] {
      const c = this.children;
      this.children = [];
      return c;
    }
    destroy(): void {}
    on(ev: string, cb: (e: unknown) => void): this {
      (this.handlers[ev] ??= []).push(cb);
      return this;
    }
  }
  class FakeGraphics extends FakeContainer {
    clear(): this { return this; }
    moveTo(): this { return this; }
    lineTo(): this { return this; }
    fill(): this { return this; }
    stroke(): this { return this; }
  }
  class FakeText extends FakeContainer {
    text = '';
  }
  const appInstances: FakeApplication[] = [];
  class FakeApplication {
    stage = new FakeContainer();
    renderer = { width: 800, height: 600 };
    canvas = document.createElement('canvas');
    init = vi.fn().mockResolvedValue(undefined);
    destroy = vi.fn();
    constructor() {
      appInstances.push(this);
    }
  }
  return { FakeContainer, FakeGraphics, FakeText, FakeApplication, appInstances };
});

const appInstances = h.appInstances as unknown as Array<{
  stage: { children: Array<{ children: Array<{ children: Array<{ handlers: Record<string, Array<(e: unknown) => void>> }> }> }> };
  init: ReturnType<typeof vi.fn>;
  destroy: ReturnType<typeof vi.fn>;
}>;

vi.mock('pixi.js', () => ({
  Application: h.FakeApplication,
  Container: h.FakeContainer,
  Graphics: h.FakeGraphics,
  Text: h.FakeText,
}));

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
    // Fire the sprite pointertap handler captured by the fake container.
    const nodeSprite = appInstances[0]!.stage.children
      .flatMap((world) => world.children)
      .flatMap((layer) => layer.children)
      .find((c) => c.handlers['pointertap']);
    nodeSprite?.handlers['pointertap']?.[0]?.({ stopPropagation: vi.fn() });
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
});
