/**
 * Single source of truth for a node's VISUAL status (BACK-FU-009 context).
 *
 * Backend `health` and the Frontend display status are DIFFERENT concepts:
 * - `health` is optional in the snapshot (free-form object; not contract-required).
 * - Some node kinds have no health concept at all (e.g. load_balancer) → their
 *   missing health means **not_applicable**, NOT "Healthy".
 * - A health-capable kind (app/redis/postgresql) with a missing value means
 *   **not_reported**, NOT "Healthy" and NOT auto-Warning/Critical.
 *
 * Incidents are handled separately — a not_applicable LB can still carry an
 * LB_IMBALANCE / NO_HEALTHY_SERVER incident (shown via the incident panel).
 *
 * Every surface (BuildingView / NodeList / NodeInspector / ARIA) MUST derive its
 * status from `resolveNodeVisualStatus` so the canvas and DOM never disagree.
 */

import type { Health } from '../api/schemas';

export type NodeVisualStatus =
  | { kind: 'health'; health: Health }
  | { kind: 'disabled' }
  | { kind: 'not_applicable' }
  | { kind: 'not_reported' };

export type HealthCapability = 'reported' | 'not_applicable';

/** Which node kinds report a health value. Unknown kinds default to 'reported'
 * so a missing value surfaces as not_reported (never a false Healthy). */
export const NODE_HEALTH_CAPABILITY: Record<string, HealthCapability> = {
  load_balancer: 'not_applicable',
  app_server: 'reported',
  redis: 'reported',
  postgresql: 'reported',
};

const KNOWN_HEALTH: ReadonlySet<string> = new Set(['Healthy', 'Warning', 'Critical', 'Down']);

export interface NodeStatusInput {
  kind: string;
  enabled: boolean;
  /** Raw health from the snapshot — may be absent, undefined, or an
   * unrecognized string. */
  health?: string | undefined;
}

export function healthCapability(kind: string): HealthCapability {
  return NODE_HEALTH_CAPABILITY[kind] ?? 'reported';
}

/** Resolve the display status. Disabled takes precedence; a missing health maps
 * to not_applicable / not_reported by the kind's capability. Never Healthy. */
export function resolveNodeVisualStatus(node: NodeStatusInput): NodeVisualStatus {
  if (node.enabled === false) return { kind: 'disabled' };
  if (node.health != null && KNOWN_HEALTH.has(node.health)) {
    return { kind: 'health', health: node.health as Health };
  }
  if (node.health != null) {
    // Present but not a value this client understands → not_reported (no fallback to Healthy).
    return { kind: 'not_reported' };
  }
  return healthCapability(node.kind) === 'not_applicable'
    ? { kind: 'not_applicable' }
    : { kind: 'not_reported' };
}

// --- appearance (one table drives colour + text + a11y for canvas and DOM) ---

/** Tone key = the DOM CSS class suffix `status-<toneKey>` and a stable label. */
export type StatusToneKey =
  | 'Healthy'
  | 'Warning'
  | 'Critical'
  | 'Down'
  | 'Disabled'
  | 'NotApplicable'
  | 'NotReported';

export interface StatusAppearance {
  toneKey: StatusToneKey;
  color: number; // Pixi fill/border colour — never green for N/A or unavailable
  border: number;
  glyph: string; // non-colour cue (also a screen-reader hint)
  pattern: 'solid' | 'dashed' | 'double' | 'hatched';
  shortText: string; // NodeList / inspector text
  ariaText: string; // screen-reader phrase
}

const HEALTH_APPEARANCE: Record<Health, StatusAppearance> = {
  Healthy: { toneKey: 'Healthy', color: 0x1e9e57, border: 0x176f3e, glyph: '✔', pattern: 'solid', shortText: 'Healthy', ariaText: 'healthy' },
  Warning: { toneKey: 'Warning', color: 0xc9820a, border: 0x8f5c07, glyph: '!', pattern: 'dashed', shortText: 'Warning', ariaText: 'warning' },
  Critical: { toneKey: 'Critical', color: 0xd43f2f, border: 0x9a2c20, glyph: '‼', pattern: 'double', shortText: 'Critical', ariaText: 'critical' },
  Down: { toneKey: 'Down', color: 0x6b5b7b, border: 0x4c3f59, glyph: '✕', pattern: 'hatched', shortText: 'Down', ariaText: 'down' },
};

const DISABLED_APPEARANCE: StatusAppearance = {
  toneKey: 'Disabled',
  color: 0x8b98a6,
  border: 0x5f6b78,
  glyph: '⏸',
  pattern: 'dashed',
  shortText: 'Disabled',
  ariaText: 'disabled',
};

// Neutral, non-green treatments — distinct glyph/text so N/A ≠ unavailable ≠ Healthy.
const NOT_APPLICABLE_APPEARANCE: StatusAppearance = {
  toneKey: 'NotApplicable',
  color: 0x5f7387, // blue-grey
  border: 0x435160,
  glyph: '—',
  pattern: 'solid',
  shortText: 'Health N/A',
  ariaText: 'health status not applicable',
};

const NOT_REPORTED_APPEARANCE: StatusAppearance = {
  toneKey: 'NotReported',
  color: 0x8b8b8b, // neutral grey
  border: 0x5f5f5f,
  glyph: '?',
  pattern: 'dashed',
  shortText: 'Status unavailable',
  ariaText: 'health status unavailable',
};

export function statusAppearance(status: NodeVisualStatus): StatusAppearance {
  switch (status.kind) {
    case 'health':
      return HEALTH_APPEARANCE[status.health];
    case 'disabled':
      return DISABLED_APPEARANCE;
    case 'not_applicable':
      return NOT_APPLICABLE_APPEARANCE;
    case 'not_reported':
      return NOT_REPORTED_APPEARANCE;
  }
}

/** Convenience: appearance directly from a node. */
export function nodeStatusAppearance(node: NodeStatusInput): StatusAppearance {
  return statusAppearance(resolveNodeVisualStatus(node));
}
