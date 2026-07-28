/**
 * Adapts a board node (from the Backend snapshot) + a grid placement into a
 * `BuildingRenderModel`. An unknown kind never breaks the scene (FE-ART-001
 * partial): it maps to a safe 'unknown' building with an "UNKNOWN" label. This
 * does NOT invent thresholds — it only carries `health`/`enabled` verbatim.
 */

import type { BoardNode } from '../nodes';
import type { NodeKind } from '../../../api/schemas';
import { kindVisual, type BuildingRenderModel } from './buildingTypes';

const KNOWN_KINDS: ReadonlySet<string> = new Set<NodeKind>([
  'load_balancer',
  'app_server',
  'redis',
  'postgresql',
]);

export function nodeToBuildingModel(
  node: BoardNode,
  position: { col: number; row: number },
): BuildingRenderModel {
  const kind: NodeKind | 'unknown' = KNOWN_KINDS.has(node.kind) ? node.kind : 'unknown';
  const visual = kindVisual(kind);
  return {
    nodeId: node.id,
    nodeKind: kind,
    gridPosition: { col: position.col, row: position.row },
    footprint: visual.footprint,
    enabled: node.enabled,
    // Carry health through as-is (may be undefined); the status resolver decides
    // how a missing value renders — never a default Healthy.
    ...(node.health != null ? { health: node.health } : {}),
    label: `${visual.label} ${node.id}`,
  };
}
