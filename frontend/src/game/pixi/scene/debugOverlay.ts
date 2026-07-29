/**
 * Debug overlay (§25): dev-only footprint outlines + coordinate/depth labels on
 * the debug layer. Off in production by default; toggled by a code/env flag, not
 * a user setting. Never blocks pointer events (eventMode 'none').
 */

import { Container, Graphics, Text } from 'pixi.js';
import { gridToScreen } from '../isometric/coordinates';
import { selectionPolygon } from '../isometric/footprint';
import { depthZIndex } from '../isometric/depth';
import type { BuildingRenderModel } from '../buildings/buildingTypes';

export function isDebugEnabled(): boolean {
  // Enabled only via an explicit env flag in dev; never on in production builds.
  return Boolean(import.meta.env?.DEV) && import.meta.env?.VITE_PIXI_DEBUG === '1';
}

export function renderDebug(layer: Container, models: BuildingRenderModel[]): void {
  layer.removeChildren().forEach((c) => c.destroy({ children: true }));
  layer.eventMode = 'none';
  for (const m of models) {
    const origin = gridToScreen(m.gridPosition.col, m.gridPosition.row);
    const poly = selectionPolygon({ col: m.gridPosition.col, row: m.gridPosition.row, footprint: m.footprint })
      .flatMap((p) => [p.x, p.y]);
    const g = new Graphics();
    g.position.set(origin.x, origin.y);
    g.poly(poly).stroke({ color: 0xff00ff, width: 1 });
    const t = new Text({
      text: `(${m.gridPosition.col},${m.gridPosition.row}) z${depthZIndex({
        col: m.gridPosition.col,
        row: m.gridPosition.row,
        footprint: m.footprint,
      })}`,
      style: { fill: 0xff00ff, fontSize: 9, fontFamily: 'monospace' },
    });
    t.position.set(origin.x, origin.y);
    layer.addChild(g);
    layer.addChild(t);
  }
}
