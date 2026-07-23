/**
 * PixiJS isometric scene (§18). Encapsulates the Pixi `Application`, a pannable
 * world container, node sprites, and selection. All the pure geometry/visual
 * logic lives in `isometric.ts`/`nodes.ts`; this file only wires Pixi.
 *
 * Lifecycle contract (§26): `destroy()` removes the window resize listener,
 * destroys the Pixi `Application` (and its children/textures), and drops all
 * references. `create()` is the only place Pixi is instantiated, so tests can
 * `vi.mock('pixi.js')`.
 */

import { Application, Container, Graphics, Text } from 'pixi.js';
import type { FederatedPointerEvent } from 'pixi.js';
import { DEFAULT_TILE, gridToScreen, layoutGrid } from './isometric';
import { nodeVisual, type BoardNode } from './nodes';

export interface GameSceneOptions {
  background?: number;
  onSelect?: (nodeId: string | null) => void;
}

interface NodeSprite {
  container: Container;
  redraw: (node: BoardNode, selected: boolean) => void;
}

export class GameScene {
  private readonly app: Application;
  private readonly world: Container;
  private readonly edgeLayer: Container;
  private readonly nodeLayer: Container;
  private readonly sprites = new Map<string, NodeSprite>();
  private readonly onSelect: ((nodeId: string | null) => void) | undefined;
  private readonly handleResize = (): void => this.recenter();

  private selectedId: string | null = null;
  private destroyed = false;
  private dragging = false;
  private dragStart = { x: 0, y: 0, wx: 0, wy: 0 };

  private constructor(app: Application, options: GameSceneOptions) {
    this.app = app;
    this.onSelect = options.onSelect;
    this.world = new Container();
    this.edgeLayer = new Container();
    this.nodeLayer = new Container();
    this.world.addChild(this.edgeLayer);
    this.world.addChild(this.nodeLayer);
    this.app.stage.addChild(this.world);

    // Background panning: drag empty space to move the camera.
    this.app.stage.eventMode = 'static';
    this.app.stage.hitArea = { contains: () => true };
    this.app.stage.on('pointerdown', this.onBackgroundDown);
    this.app.stage.on('pointermove', this.onBackgroundMove);
    this.app.stage.on('pointerup', this.onBackgroundUp);
    this.app.stage.on('pointerupoutside', this.onBackgroundUp);

    window.addEventListener('resize', this.handleResize);
    this.recenter();
  }

  static async create(container: HTMLElement, options: GameSceneOptions = {}): Promise<GameScene> {
    const app = new Application();
    await app.init({
      background: options.background ?? 0x0f1419,
      resizeTo: container,
      antialias: true,
    });
    container.appendChild(app.canvas);
    return new GameScene(app, options);
  }

  /** Reconcile the board with a node list + connections (add/update/remove). */
  sync(nodes: BoardNode[], connections: Array<[string, string]>): void {
    if (this.destroyed) return;
    const layout = layoutGrid(nodes.map((n) => n.id));
    const present = new Set(nodes.map((n) => n.id));

    for (const [id, sprite] of this.sprites) {
      if (!present.has(id)) {
        sprite.container.destroy({ children: true });
        this.sprites.delete(id);
      }
    }

    for (const node of nodes) {
      const pos = layout.get(node.id) ?? { x: 0, y: 0 };
      const screen = gridToScreen(pos.x, pos.y);
      let sprite = this.sprites.get(node.id);
      if (!sprite) {
        sprite = this.createNodeSprite(node.id);
        this.sprites.set(node.id, sprite);
        this.nodeLayer.addChild(sprite.container);
      }
      sprite.container.position.set(screen.x, screen.y);
      sprite.redraw(node, node.id === this.selectedId);
    }

    this.drawEdges(connections);
  }

  setSelection(nodeId: string | null): void {
    this.selectedId = nodeId;
    for (const [id, sprite] of this.sprites) {
      // Redraw only the border/selection ring; cheap enough for MVP sizes.
      const node = (sprite.container as Container & { _node?: BoardNode })._node;
      if (node) sprite.redraw(node, id === nodeId);
    }
  }

  resize(): void {
    if (this.destroyed) return;
    this.recenter();
  }

  destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;
    window.removeEventListener('resize', this.handleResize);
    this.sprites.clear();
    // Destroys stage children, listeners, and GPU resources.
    this.app.destroy(true, { children: true, texture: true });
  }

  // -- internals -------------------------------------------------------------

  private createNodeSprite(id: string): NodeSprite {
    const c = new Container() as Container & { _node?: BoardNode };
    c.eventMode = 'static';
    c.cursor = 'pointer';
    const g = new Graphics();
    const label = new Text({
      text: '',
      style: { fill: 0xffffff, fontSize: 12, fontFamily: 'monospace' },
    });
    label.position.set(-DEFAULT_TILE.width / 4, -8);
    c.addChild(g);
    c.addChild(label);
    c.on('pointertap', (e: FederatedPointerEvent) => {
      e.stopPropagation();
      this.select(id);
    });

    const redraw = (node: BoardNode, selected: boolean): void => {
      c._node = node;
      const v = nodeVisual(node);
      const w = DEFAULT_TILE.width / 2;
      const h = DEFAULT_TILE.height;
      g.clear();
      // Isometric diamond.
      g.moveTo(0, -h / 2)
        .lineTo(w, 0)
        .lineTo(0, h / 2)
        .lineTo(-w, 0)
        .lineTo(0, -h / 2)
        .fill({ color: v.color })
        .stroke({ color: selected ? 0xffffff : v.border, width: selected ? 3 : 1 });
      label.text = `${v.glyph} ${v.label}`;
    };

    return { container: c, redraw };
  }

  private drawEdges(connections: Array<[string, string]>): void {
    this.edgeLayer.removeChildren().forEach((child) => child.destroy());
    const g = new Graphics();
    for (const [src, dst] of connections) {
      const a = this.sprites.get(src)?.container.position;
      const b = this.sprites.get(dst)?.container.position;
      if (!a || !b) continue;
      g.moveTo(a.x, a.y).lineTo(b.x, b.y).stroke({ color: 0x5a6470, width: 2 });
    }
    this.edgeLayer.addChild(g);
  }

  private select(nodeId: string | null): void {
    this.setSelection(nodeId);
    this.onSelect?.(nodeId);
  }

  private recenter(): void {
    const { width, height } = this.app.renderer;
    this.world.position.set(width / 2, height / 3);
  }

  private readonly onBackgroundDown = (e: FederatedPointerEvent): void => {
    this.dragging = true;
    this.dragStart = { x: e.global.x, y: e.global.y, wx: this.world.x, wy: this.world.y };
  };

  private readonly onBackgroundMove = (e: FederatedPointerEvent): void => {
    if (!this.dragging) return;
    this.world.position.set(
      this.dragStart.wx + (e.global.x - this.dragStart.x),
      this.dragStart.wy + (e.global.y - this.dragStart.y),
    );
  };

  private readonly onBackgroundUp = (): void => {
    this.dragging = false;
  };
}
