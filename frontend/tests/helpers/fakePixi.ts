/**
 * Shared Pixi fake for unit tests (no WebGL/canvas). Import via:
 *   vi.mock('pixi.js', async () => await import('../helpers/fakePixi'));
 * Supports the Pixi surface the scene/building/asset code uses.
 */

import { vi } from 'vitest';

export class Container {
  label = '';
  zIndex = 0;
  visible = true;
  sortableChildren = false;
  eventMode = '';
  cursor = '';
  hitArea: unknown = null;
  position = { _x: 0, _y: 0, set(x: number, y: number) { this._x = x; this._y = y; }, get x() { return this._x; }, get y() { return this._y; } };
  children: Container[] = [];
  parent: Container | null = null;
  handlers: Record<string, Array<(e: unknown) => void>> = {};
  destroyed = false;

  addChild<T extends Container>(c: T): T {
    c.parent = this;
    this.children.push(c);
    return c;
  }
  removeChildren(): Container[] {
    const c = this.children;
    c.forEach((child) => (child.parent = null));
    this.children = [];
    return c;
  }
  removeAllListeners(): this {
    this.handlers = {};
    return this;
  }
  destroy(): void {
    this.destroyed = true;
    // Real Pixi removes a destroyed node from its parent.
    if (this.parent) {
      this.parent.children = this.parent.children.filter((c) => c !== this);
      this.parent = null;
    }
  }
  on(ev: string, cb: (e: unknown) => void): this {
    (this.handlers[ev] ??= []).push(cb);
    return this;
  }
}

export class Graphics extends Container {
  clear(): this { return this; }
  moveTo(): this { return this; }
  lineTo(): this { return this; }
  poly(): this { return this; }
  rect(): this { return this; }
  fill(): this { return this; }
  stroke(): this { return this; }
}

export class Text extends Container {
  text = '';
  style: unknown = {};
  constructor(opts?: { text?: string; style?: unknown }) {
    super();
    if (opts?.text !== undefined) this.text = opts.text;
    if (opts?.style !== undefined) this.style = opts.style;
  }
}

export const Texture = {
  from: vi.fn(() => ({ destroy: vi.fn() })),
};

export const appInstances: Application[] = [];
export class Application {
  stage = new Container();
  renderer = { width: 800, height: 600 };
  canvas = typeof document !== 'undefined' ? document.createElement('canvas') : ({} as HTMLCanvasElement);
  init = vi.fn().mockResolvedValue(undefined);
  destroy = vi.fn();
  constructor() {
    appInstances.push(this);
  }
}

/** Recursively find the first descendant with a handler for `ev`. */
export function findHandler(root: Container, ev: string): Container | undefined {
  if (root.handlers[ev]?.length) return root;
  for (const c of root.children) {
    const found = findHandler(c, ev);
    if (found) return found;
  }
  return undefined;
}
