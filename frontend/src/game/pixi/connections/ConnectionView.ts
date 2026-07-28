/**
 * ConnectionView (§22): renders the connection edges on the dedicated
 * connections layer. PR B keeps the existing simple-line style (final styling is
 * PR C/D); it only moves edges onto their own layer and diffs by a stable key so
 * ADD/REMOVE reflect immediately and endpoints follow moved buildings.
 */

import { Container, Graphics } from 'pixi.js';

export type Edge = [string, string];
export type PositionLookup = (nodeId: string) => { x: number; y: number } | undefined;

export function connectionKey(edge: Edge): string {
  return `${edge[0]}->${edge[1]}`;
}

export class ConnectionView {
  private readonly graphics = new Graphics();

  constructor(layer: Container) {
    this.graphics.label = 'connections';
    layer.addChild(this.graphics);
  }

  /** Redraw all edges from current building positions. */
  sync(edges: Edge[], positionOf: PositionLookup): void {
    this.graphics.clear();
    for (const [src, dst] of edges) {
      const a = positionOf(src);
      const b = positionOf(dst);
      if (!a || !b) continue;
      this.graphics.moveTo(a.x, a.y).lineTo(b.x, b.y).stroke({ color: 0x5a6470, width: 2 });
    }
  }

  destroy(): void {
    this.graphics.destroy();
  }
}
