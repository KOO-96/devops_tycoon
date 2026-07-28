/**
 * Visual mapping for board nodes (§19). Status is conveyed by colour AND an
 * icon glyph AND a text label / border pattern — never colour alone (§25).
 */

import type { Health, NodeKind, SimulationSnapshot, SnapshotNode } from '../../api/schemas';

export interface BoardNode {
  id: string;
  kind: NodeKind;
  health: Health;
  enabled: boolean;
}

export interface NodeVisual {
  color: number; // fill colour
  border: number; // border colour
  glyph: string; // icon glyph (also a screen-reader hint)
  label: string; // short kind label
  pattern: 'solid' | 'dashed' | 'double' | 'hatched'; // non-colour status cue
}

const KIND_LABEL: Record<NodeKind, string> = {
  load_balancer: 'LB',
  app_server: 'APP',
  redis: 'REDIS',
  postgresql: 'DB',
};

const KIND_GLYPH: Record<NodeKind, string> = {
  load_balancer: '⇄',
  app_server: '▣',
  redis: '◆',
  postgresql: '⛁',
};

const HEALTH_COLOR: Record<Health, number> = {
  Healthy: 0x2ecc71,
  Warning: 0xf1c40f,
  Critical: 0xe67e22,
  Down: 0xe74c3c,
};

const HEALTH_PATTERN: Record<Health, NodeVisual['pattern']> = {
  Healthy: 'solid',
  Warning: 'dashed',
  Critical: 'double',
  Down: 'hatched',
};

export function nodeVisual(node: BoardNode): NodeVisual {
  const color = node.enabled ? HEALTH_COLOR[node.health] : 0x7f8c8d;
  return {
    color,
    border: node.enabled ? 0x1a1a1a : 0x555555,
    glyph: KIND_GLYPH[node.kind],
    label: KIND_LABEL[node.kind] + (node.enabled ? '' : ' (off)'),
    pattern: node.enabled ? HEALTH_PATTERN[node.health] : 'dashed',
  };
}

/** Human-readable one-line status for the accessible node list / a11y summary. */
export function nodeStatusText(node: BoardNode): string {
  const state = node.enabled ? node.health : 'Disabled';
  return `${KIND_LABEL[node.kind]} ${node.id}: ${state}`;
}

/** Flatten a snapshot's four node collections into a stable board-node list. */
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
        // Some node kinds (e.g. load_balancer) omit `health` in the snapshot;
        // default to Healthy so the board never renders an undefined status.
        health: node.health ?? 'Healthy',
        enabled: node.enabled,
      });
    }
  }
  return out;
}
