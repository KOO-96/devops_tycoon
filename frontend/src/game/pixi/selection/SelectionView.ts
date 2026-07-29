/**
 * SelectionView (§23): draws the selection highlight on the dedicated selection
 * layer (above buildings/status) so it is never hidden. It draws a footprint
 * ring at the selected building's screen position; the actual selection state is
 * owned by the scene/store.
 */

import { Container, Graphics } from 'pixi.js';
import { gridToScreen } from '../isometric/coordinates';
import { selectionPolygon, type GridPlacement } from '../isometric/footprint';

export class SelectionView {
  private readonly ring = new Graphics();

  constructor(layer: Container) {
    this.ring.label = 'selection-ring';
    this.ring.visible = false;
    layer.addChild(this.ring);
  }

  /** Show the ring around a placement; pass null to hide. */
  show(placement: GridPlacement | null): void {
    if (!placement) {
      this.ring.visible = false;
      return;
    }
    const origin = gridToScreen(placement.col, placement.row);
    const poly = selectionPolygon(placement).flatMap((p) => [p.x, p.y]);
    this.ring.clear();
    this.ring.position.set(origin.x, origin.y);
    this.ring
      .poly(poly)
      .stroke({ color: 0x00b3b3, width: 3 });
    this.ring.visible = true;
  }

  destroy(): void {
    this.ring.destroy();
  }
}
