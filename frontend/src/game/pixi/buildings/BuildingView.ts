/**
 * BuildingView (§14): a Pixi Container rendering ONE building from a
 * `BuildingRenderModel`. It draws a DEVELOPMENT placeholder (simple geometry +
 * label), not final art. It never calls the API and never subscribes to the
 * store — the scene pushes a render model in.
 *
 * Status uses colour AND border-pattern AND the label (§25). Anchor is the
 * footprint bottom-center, so taller final sprites won't shift the base (§12).
 */

import { Container, Graphics, Text } from 'pixi.js';
import type { FederatedPointerEvent } from 'pixi.js';
import { HALF_TILE_HEIGHT, HALF_TILE_WIDTH } from '../isometric/coordinates';
import { selectionPolygon } from '../isometric/footprint';
import { depthZIndex } from '../isometric/depth';
import { gridToScreen } from '../isometric/coordinates';
import {
  HEALTH_COLOR,
  HEALTH_PATTERN,
  kindVisual,
  type BuildingRenderModel,
} from './buildingTypes';

export class BuildingView {
  readonly container: Container;
  private readonly slab: Graphics;
  private readonly body: Graphics;
  private readonly label: Text;
  private model: BuildingRenderModel;

  constructor(model: BuildingRenderModel, onSelect: (nodeId: string) => void) {
    this.model = model;
    const c = new Container();
    c.label = `building:${model.nodeId}`;
    c.eventMode = 'static';
    c.cursor = 'pointer';
    this.slab = new Graphics();
    this.body = new Graphics();
    this.label = new Text({
      text: '',
      style: { fill: 0x1b2b3a, fontSize: 11, fontFamily: 'monospace' },
    });
    c.addChild(this.slab);
    c.addChild(this.body);
    c.addChild(this.label);
    c.on('pointertap', (e: FederatedPointerEvent) => {
      e.stopPropagation();
      onSelect(model.nodeId);
    });
    this.container = c;
    this.applyPosition();
    this.redraw(false);
  }

  get nodeId(): string {
    return this.model.nodeId;
  }

  /** Update from a new render model (position + visuals). Reused, not recreated. */
  update(model: BuildingRenderModel, selected: boolean): void {
    const moved =
      model.gridPosition.col !== this.model.gridPosition.col ||
      model.gridPosition.row !== this.model.gridPosition.row ||
      model.footprint.width !== this.model.footprint.width ||
      model.footprint.height !== this.model.footprint.height;
    this.model = model;
    if (moved) this.applyPosition();
    this.redraw(selected);
  }

  setSelected(selected: boolean): void {
    this.redraw(selected);
  }

  destroy(): void {
    this.container.removeAllListeners();
    this.container.destroy({ children: true });
  }

  // -- internals --

  private applyPosition(): void {
    const { col, row } = this.model.gridPosition;
    const p = gridToScreen(col, row);
    this.container.position.set(p.x, p.y);
    this.container.zIndex = depthZIndex({ col, row, footprint: this.model.footprint });
  }

  private redraw(selected: boolean): void {
    const kv = kindVisual(this.model.nodeKind);
    const fp = this.model.footprint;
    // Footprint slab (diamond covering the footprint), relative to base tile.
    const poly = selectionPolygon({ col: 0, row: 0, footprint: fp }).flatMap((pt) => [pt.x, pt.y]);
    this.slab.clear();
    this.slab.poly(poly).fill({ color: 0xdfeaf5, alpha: 0.85 }).stroke({ color: 0xb9cbdd, width: 1 });

    // Simple cuboid silhouette rising from the footprint center-front.
    const cx = ((fp.width - fp.height) * HALF_TILE_WIDTH) / 2;
    const baseY = (fp.width + fp.height) * HALF_TILE_HEIGHT * 0.5;
    const bw = HALF_TILE_WIDTH * Math.min(fp.width, 2) * 0.7;
    const bh = 26 + 8 * Math.max(fp.width, fp.height);
    const fill = this.model.enabled ? kv.baseColor : 0x8b98a6;
    // Defensive: an unexpected/missing health must never yield an undefined
    // colour (Pixi throws). Fall back to the Healthy tokens.
    const health = HEALTH_COLOR[this.model.health] ?? HEALTH_COLOR.Healthy;
    const pattern = this.model.enabled
      ? (HEALTH_PATTERN[this.model.health] ?? 'solid')
      : 'dashed';
    const border = selected ? 0x00b3b3 : health;
    const borderW = selected ? 3 : pattern === 'double' ? 3 : pattern === 'solid' ? 2 : 1;

    this.body.clear();
    this.body
      .rect(cx - bw / 2, baseY - bh, bw, bh)
      .fill({ color: fill })
      .stroke({ color: border, width: borderW });
    // Non-colour health cue: a small notch pattern count.
    const notches = pattern === 'hatched' ? 3 : pattern === 'double' ? 2 : pattern === 'dashed' ? 1 : 0;
    for (let i = 0; i < notches; i++) {
      this.body.rect(cx - bw / 2 + 3 + i * 5, baseY - bh + 3, 3, 3).fill({ color: border });
    }

    this.label.text = `${kv.glyph} ${this.model.label}`;
    this.label.position.set(cx - bw / 2, baseY - bh - 14);
  }
}
