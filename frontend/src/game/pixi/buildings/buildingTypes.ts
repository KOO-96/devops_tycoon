/**
 * Building render model + kind→visual mapping (PR B). This is the data contract
 * BuildingView renders; it is derived from a Backend snapshot node by
 * `nodeBuildingAdapter`, never from the API or the store directly.
 */

import type { Health, NodeKind } from '../../../api/schemas';
import type { TileFootprint } from '../isometric/footprint';

/** Marker so grep/reviewers can confirm these are not final art. */
export const DEVELOPMENT_PLACEHOLDER_NOT_FINAL_ART = 'DEVELOPMENT_PLACEHOLDER_NOT_FINAL_ART';

export interface BuildingRenderModel {
  nodeId: string;
  /** The backend node kind, or 'unknown' when unrecognized (FE-ART-001 fallback). */
  nodeKind: NodeKind | 'unknown';
  gridPosition: { col: number; row: number };
  footprint: TileFootprint;
  enabled: boolean;
  /** Optional — some kinds (load_balancer) omit health; status is resolved from
   * the kind's capability, never defaulted to Healthy. */
  health?: Health;
  label: string;
}

export interface KindVisual {
  label: string;
  glyph: string;
  footprint: TileFootprint;
  baseColor: number;
}

// Proposed placeholder visuals (asset-style-guide Proposed palette). Footprints
// are Proposed defaults for PR B placeholders — final sizes come with real art.
const KIND_VISUAL: Record<NodeKind, KindVisual> = {
  load_balancer: { label: 'LB', glyph: '⇄', footprint: { width: 2, height: 2 }, baseColor: 0x4aa3ff },
  app_server: { label: 'APP', glyph: '▣', footprint: { width: 1, height: 1 }, baseColor: 0x6fbf73 },
  redis: { label: 'REDIS', glyph: '◆', footprint: { width: 1, height: 1 }, baseColor: 0xff8a5c },
  postgresql: { label: 'DB', glyph: '⛁', footprint: { width: 2, height: 2 }, baseColor: 0x9b8cff },
};

const UNKNOWN_VISUAL: KindVisual = {
  label: 'UNKNOWN',
  glyph: '?',
  footprint: { width: 1, height: 1 },
  baseColor: 0x8b98a6,
};

export function kindVisual(kind: NodeKind | 'unknown'): KindVisual {
  if (kind === 'unknown') return UNKNOWN_VISUAL;
  return KIND_VISUAL[kind] ?? UNKNOWN_VISUAL;
}

// Health colour/pattern now live in the shared status resolver
// (`game/nodeStatus.ts`) so canvas and DOM share one source of truth.
