/**
 * Board node projection from the snapshot. Status (colour/glyph/text) is derived
 * via the shared `resolveNodeVisualStatus`/`statusAppearance` so the canvas and
 * DOM never disagree, and a missing `health` is NEVER shown as Healthy (§25).
 */

import type { Health, NodeKind, SimulationSnapshot, SnapshotNode } from '../../api/schemas';
import { nodeStatusAppearance } from '../nodeStatus';

export interface BoardNode {
  id: string;
  kind: NodeKind;
  /** Optional: some kinds (load_balancer) omit health in the snapshot. */
  health?: Health;
  enabled: boolean;
}

const KIND_LABEL: Record<NodeKind, string> = {
  load_balancer: 'LB',
  app_server: 'APP',
  redis: 'REDIS',
  postgresql: 'DB',
};

/** Human-readable one-line status for the accessible node list / a11y summary. */
export function nodeStatusText(node: BoardNode): string {
  const appearance = nodeStatusAppearance(node);
  return `${KIND_LABEL[node.kind]} ${node.id}: ${appearance.shortText}`;
}

/** Screen-reader phrase distinguishing not_applicable vs not_reported. */
export function nodeStatusAria(node: BoardNode): string {
  const appearance = nodeStatusAppearance(node);
  return `${KIND_LABEL[node.kind]} ${node.id}, ${appearance.ariaText}`;
}

/** Flatten a snapshot's four node collections into a stable board-node list.
 * `health` is carried through as-is (may be undefined) — the status resolver,
 * not a default, decides how a missing value is shown. */
export function snapshotToBoardNodes(snapshot: SimulationSnapshot | null): BoardNode[] {
  if (!snapshot) return [];
  const groups: Array<Record<string, SnapshotNode>> = [
    snapshot.load_balancers,
    snapshot.app_servers,
    snapshot.caches,
    snapshot.databases,
  ];
  const out: BoardNode[] = [];
  for (const group of groups) {
    for (const node of Object.values(group ?? {})) {
      out.push({
        id: node.id,
        kind: node.kind,
        ...(node.health != null ? { health: node.health } : {}),
        enabled: node.enabled,
      });
    }
  }
  return out;
}
