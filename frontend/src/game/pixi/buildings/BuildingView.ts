/**
 * BuildingView (§14, §17): a Pixi Container rendering ONE building from a
 * `BuildingRenderModel`. It shows a DEVELOPMENT placeholder — a generated Sprite
 * (from the injected AssetManager) when a texture handle is provided, else a drawn
 * silhouette. It never calls the API and never subscribes to the store.
 *
 * The STATUS overlay (border pattern + notches + glyph + label) is drawn SEPARATELY
 * from the texture, so health / N/A / unavailable / incident cues never depend on
 * the art and a missing texture never reads as a false Healthy (§25). The view does
 * not own shared textures — it holds an AssetHandle and releases it on destroy or
 * texture swap; the AssetManager owns/frees the texture.
 */

import { Container, Graphics, Sprite, Text } from 'pixi.js';
import type { FederatedPointerEvent } from 'pixi.js';
import { HALF_TILE_HEIGHT, HALF_TILE_WIDTH } from '../isometric/coordinates';
import { selectionPolygon } from '../isometric/footprint';
import { depthZIndex } from '../isometric/depth';
import { gridToScreen } from '../isometric/coordinates';
import { kindVisual, type BuildingRenderModel } from './buildingTypes';
import { resolveNodeVisualStatus, statusAppearance } from '../../nodeStatus';
import type { AssetHandle } from '../assets/AssetManager';
import type { IncidentViewModel } from '../../incidentModel';

export class BuildingView {
  readonly container: Container;
  private readonly slab: Graphics;
  private readonly bodyFill: Graphics;
  private readonly statusOverlay: Graphics;
  private readonly incidentBadge: Graphics;
  private readonly label: Text;
  private sprite: Sprite | null = null;
  private handle: AssetHandle | null = null;
  private model: BuildingRenderModel;
  private selected = false;
  private incidents: IncidentViewModel[] = [];

  constructor(model: BuildingRenderModel, onSelect: (nodeId: string) => void) {
    this.model = model;
    const c = new Container();
    c.label = `building:${model.nodeId}`;
    c.eventMode = 'static';
    c.cursor = 'pointer';
    this.slab = new Graphics();
    this.bodyFill = new Graphics();
    this.statusOverlay = new Graphics();
    this.incidentBadge = new Graphics();
    this.label = new Text({
      text: '',
      style: { fill: 0x1b2b3a, fontSize: 11, fontFamily: 'monospace' },
    });
    // Order: slab → body fill → (sprite inserted here) → status overlay → incident → label.
    c.addChild(this.slab);
    c.addChild(this.bodyFill);
    c.addChild(this.statusOverlay);
    c.addChild(this.incidentBadge);
    c.addChild(this.label);
    c.on('pointertap', (e: FederatedPointerEvent) => {
      e.stopPropagation();
      onSelect(model.nodeId);
    });
    this.container = c;
    this.applyPosition();
    this.redraw();
  }

  get nodeId(): string {
    return this.model.nodeId;
  }

  /** Attach a resolved asset handle (texture). Replaces + releases any prior handle.
   * Safe to call after the requested art loads (progressive enhancement). */
  setTexture(handle: AssetHandle): void {
    const prev = this.handle;
    this.handle = handle;
    if (handle.texture) {
      if (!this.sprite) {
        this.sprite = new Sprite(handle.texture);
        this.sprite.anchor.set(0.5, 1);
        // Sprite goes above the body fill, below the status overlay.
        this.container.addChildAt(this.sprite, 2);
      } else {
        this.sprite.texture = handle.texture;
      }
      this.positionSprite();
    }
    if (prev && prev !== handle) prev.release();
    this.redraw();
  }

  /** Current asset handle (or null). */
  getHandle(): AssetHandle | null {
    return this.handle;
  }

  update(model: BuildingRenderModel, selected: boolean): void {
    const moved =
      model.gridPosition.col !== this.model.gridPosition.col ||
      model.gridPosition.row !== this.model.gridPosition.row ||
      model.footprint.width !== this.model.footprint.width ||
      model.footprint.height !== this.model.footprint.height;
    this.model = model;
    this.selected = selected;
    if (moved) {
      this.applyPosition();
      this.positionSprite();
    }
    this.redraw();
  }

  setSelected(selected: boolean): void {
    this.selected = selected;
    this.redraw();
  }

  /** Set the deduped incidents targeting this node (separate from health). */
  setIncidents(incidents: IncidentViewModel[]): void {
    this.incidents = incidents;
    this.redraw();
  }

  destroy(): void {
    this.container.removeAllListeners();
    // Release the shared texture reference; the AssetManager owns/frees the texture.
    this.handle?.release();
    this.handle = null;
    this.sprite = null;
    this.container.destroy({ children: true });
  }

  // -- internals --

  private applyPosition(): void {
    const { col, row } = this.model.gridPosition;
    const p = gridToScreen(col, row);
    this.container.position.set(p.x, p.y);
    this.container.zIndex = depthZIndex({ col, row, footprint: this.model.footprint });
  }

  private bodyMetrics(): { cx: number; baseY: number; bw: number; bh: number } {
    const fp = this.model.footprint;
    const cx = ((fp.width - fp.height) * HALF_TILE_WIDTH) / 2;
    const baseY = (fp.width + fp.height) * HALF_TILE_HEIGHT * 0.5;
    const bw = HALF_TILE_WIDTH * Math.min(fp.width, 2) * 0.7;
    const bh = 26 + 8 * Math.max(fp.width, fp.height);
    return { cx, baseY, bw, bh };
  }

  private positionSprite(): void {
    if (!this.sprite) return;
    const { cx, baseY, bw, bh } = this.bodyMetrics();
    this.sprite.width = bw;
    this.sprite.height = bh;
    this.sprite.position.set(cx, baseY);
  }

  private redraw(): void {
    const kv = kindVisual(this.model.nodeKind);
    const fp = this.model.footprint;
    const { cx, baseY, bw, bh } = this.bodyMetrics();

    // Footprint slab (diamond covering the footprint), relative to base tile.
    const poly = selectionPolygon({ col: 0, row: 0, footprint: fp }).flatMap((pt) => [pt.x, pt.y]);
    this.slab.clear();
    this.slab.poly(poly).fill({ color: 0xdfeaf5, alpha: 0.85 }).stroke({ color: 0xb9cbdd, width: 1 });

    const status = resolveNodeVisualStatus({
      kind: this.model.nodeKind,
      enabled: this.model.enabled,
      health: this.model.health,
    });
    const appearance = statusAppearance(status);
    const fill = status.kind === 'disabled' ? 0x8b98a6 : kv.baseColor;

    // Body fill: drawn only when there is no sprite (the Sprite replaces it). The
    // silhouette is a texture concern; status is drawn separately below.
    this.bodyFill.clear();
    if (!this.sprite) {
      this.bodyFill.rect(cx - bw / 2, baseY - bh, bw, bh).fill({ color: fill });
    }

    // Status overlay: border pattern + notches — SEPARATE from the texture, so it
    // reads over any art (or none). Selection is a distinct accent, not health.
    const pattern = appearance.pattern;
    const border = this.selected ? 0x00b3b3 : appearance.color;
    const borderW = this.selected ? 3 : pattern === 'double' ? 3 : pattern === 'solid' ? 2 : 1;
    this.statusOverlay.clear();
    this.statusOverlay.rect(cx - bw / 2, baseY - bh, bw, bh).stroke({ color: border, width: borderW });
    const notches = pattern === 'hatched' ? 3 : pattern === 'double' ? 2 : pattern === 'dashed' ? 1 : 0;
    for (let i = 0; i < notches; i++) {
      this.statusOverlay.rect(cx - bw / 2 + 3 + i * 5, baseY - bh + 3, 3, 3).fill({ color: border });
    }

    // Incident badge: a small marker at the top-right when incidents target this
    // node — separate from the health border, never mutating health.
    this.incidentBadge.clear();
    if (this.incidents.length > 0) {
      this.incidentBadge
        .circle(cx + bw / 2, baseY - bh, 5)
        .fill({ color: 0xd43f2f })
        .stroke({ color: 0xffffff, width: 1 });
    }

    // Label = kind glyph + status glyph + node label + optional incident count.
    const incidentTag = this.incidents.length > 0 ? ` ⚑${this.incidents.length}` : '';
    this.label.text = `${kv.glyph} ${appearance.glyph} ${this.model.label}${incidentTag}`;
    this.label.position.set(cx - bw / 2, baseY - bh - 14);
  }
}
