/**
 * Explicit, typed scene layer registry (§8–§9). Layers are created once and
 * ordered explicitly; Selection sits above Status which sits above Effects, so
 * incident/selection overlays are never hidden by buildings. Debug is off by
 * default. DOM HUD is NOT a Pixi layer.
 */

import { Container } from 'pixi.js';

export type SceneLayerName =
  | 'ground'
  | 'grid'
  | 'connections'
  | 'buildingBase'
  | 'buildings'
  | 'decorations'
  | 'effects'
  | 'status'
  | 'selection'
  | 'debug';

/** Draw order, back → front. Index also serves as the container zIndex. */
export const LAYER_ORDER: readonly SceneLayerName[] = [
  'ground',
  'grid',
  'connections',
  'buildingBase',
  'buildings',
  'decorations',
  'effects',
  'status',
  'selection',
  'debug',
];

export class SceneLayers {
  private readonly layers = new Map<SceneLayerName, Container>();

  /** Create all layers under `parent` in explicit order. */
  constructor(parent: Container, debugEnabled = false) {
    LAYER_ORDER.forEach((name, i) => {
      const c = new Container();
      c.label = `layer:${name}`;
      c.zIndex = i;
      if (name === 'debug') c.visible = debugEnabled;
      // The buildings layer sorts its children by depth zIndex.
      if (name === 'buildings') c.sortableChildren = true;
      this.layers.set(name, c);
      parent.addChild(c);
    });
  }

  get(name: SceneLayerName): Container {
    const c = this.layers.get(name);
    if (!c) throw new Error(`unknown scene layer ${name}`);
    return c;
  }

  setDebugVisible(visible: boolean): void {
    this.get('debug').visible = visible;
  }

  /** Destroy all layer children; layers themselves are freed with the stage. */
  clear(): void {
    for (const c of this.layers.values()) {
      c.removeChildren().forEach((child) => child.destroy({ children: true }));
    }
  }
}
