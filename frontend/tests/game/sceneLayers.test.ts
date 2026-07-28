import { describe, expect, it, vi } from 'vitest';

vi.mock('pixi.js', async () => await import('../helpers/fakePixi'));

import { Container } from '../helpers/fakePixi';
import { LAYER_ORDER, SceneLayers } from '../../src/game/pixi/scene/sceneLayers';

describe('SceneLayers', () => {
  it('creates all layers once, in explicit back→front order', () => {
    const parent = new Container() as unknown as import('pixi.js').Container;
    const layers = new SceneLayers(parent);
    // Every named layer resolves.
    for (const name of LAYER_ORDER) expect(layers.get(name)).toBeDefined();
    // zIndex ascends with LAYER_ORDER; selection above buildings, above connections.
    const z = (n: (typeof LAYER_ORDER)[number]): number => (layers.get(n) as unknown as { zIndex: number }).zIndex;
    expect(z('connections')).toBeLessThan(z('buildings'));
    expect(z('buildings')).toBeLessThan(z('status'));
    expect(z('status')).toBeLessThan(z('selection'));
  });

  it('makes the buildings layer sortable and hides debug by default', () => {
    const parent = new Container() as unknown as import('pixi.js').Container;
    const layers = new SceneLayers(parent);
    expect((layers.get('buildings') as unknown as { sortableChildren: boolean }).sortableChildren).toBe(true);
    expect((layers.get('debug') as unknown as { visible: boolean }).visible).toBe(false);
  });

  it('can enable debug explicitly', () => {
    const parent = new Container() as unknown as import('pixi.js').Container;
    const layers = new SceneLayers(parent, true);
    expect((layers.get('debug') as unknown as { visible: boolean }).visible).toBe(true);
  });

  it('throws on an unknown layer name', () => {
    const parent = new Container() as unknown as import('pixi.js').Container;
    const layers = new SceneLayers(parent);
    expect(() => layers.get('nope' as never)).toThrow();
  });
});
