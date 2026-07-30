/**
 * Incident overlay policy (POLICY-C-FU-003). Derives a stable, deduped, bounded
 * view-model from `summary.active_incidents`.
 *
 * Contract facts this obeys (verified against the backend):
 *  - The only fields available are `type`, `target`, `phase`. There is NO separate
 *    severity enum, so the Frontend NEVER invents severity.
 *  - Phases are WARNING / ACTIVE / RECOVERING / RECOVERED.
 *  - Incidents are separate from node health: an incident is shown as its own
 *    overlay/badge and NEVER converted into a `health=Critical`.
 *
 * Determinism: the snapshot array may contain duplicate (type, target) rows and
 * has no reliable visual ordering, so we dedupe by a stable key and sort by a
 * fixed (phase-priority, type, target) order — never randomly.
 */

import type { IncidentSummary } from '../api/schemas';

export type IncidentPhase = 'WARNING' | 'ACTIVE' | 'RECOVERING' | 'RECOVERED';

/**
 * Max incidents drawn as individual overlays before collapsing to an overflow
 * summary. PROPOSED (not an SLA): sized to stay legible on a 1280×720 board and
 * to be confirmed against real-browser measurement. See visual-asset-budget.md.
 */
export const MAX_VISIBLE_INCIDENTS = 6;

const PHASE_PRIORITY: Record<IncidentPhase, number> = {
  ACTIVE: 0,
  WARNING: 1,
  RECOVERING: 2,
  RECOVERED: 3,
};

export interface IncidentViewModel {
  key: string;
  type: string;
  target: string;
  phase: IncidentPhase;
}

export interface IncidentOverlayModel {
  /** Deduped + sorted incidents that fit within the visible cap. */
  visible: IncidentViewModel[];
  /** How many deduped incidents were hidden by the cap. */
  overflowCount: number;
  /** Total deduped active incidents (visible + overflow). */
  total: number;
}

function normalizePhase(phase: string | null): IncidentPhase {
  switch (phase) {
    case 'WARNING':
    case 'ACTIVE':
    case 'RECOVERING':
    case 'RECOVERED':
      return phase;
    default:
      // Unknown/absent phase → treat as ACTIVE (present-but-unclassified), never
      // dropped and never invented as a severity.
      return 'ACTIVE';
  }
}

/** Stable identity for an incident. `type:target` — the backend has no incident id
 * in the summary, so (type, target) is the stable key. */
export function incidentKey(inc: { type: string | null; target: string | null }): string {
  return `${inc.type ?? 'incident'}:${inc.target ?? 'system'}`;
}

/**
 * Dedupe by stable key (keeping the highest-priority phase seen for that key),
 * drop RECOVERED (resolved → removed, never left active), and sort deterministically.
 */
export function dedupeIncidents(incidents: readonly IncidentSummary[]): IncidentViewModel[] {
  const byKey = new Map<string, IncidentViewModel>();
  for (const raw of incidents) {
    const phase = normalizePhase(raw.phase);
    const vm: IncidentViewModel = {
      key: incidentKey(raw),
      type: raw.type ?? 'Incident',
      target: raw.target ?? 'system',
      phase,
    };
    const existing = byKey.get(vm.key);
    if (!existing || PHASE_PRIORITY[phase] < PHASE_PRIORITY[existing.phase]) {
      byKey.set(vm.key, vm);
    }
  }
  const active = [...byKey.values()].filter((vm) => vm.phase !== 'RECOVERED');
  active.sort((a, b) => {
    const p = PHASE_PRIORITY[a.phase] - PHASE_PRIORITY[b.phase];
    if (p !== 0) return p;
    if (a.type !== b.type) return a.type < b.type ? -1 : 1;
    if (a.target !== b.target) return a.target < b.target ? -1 : 1;
    return 0;
  });
  return active;
}

/** Build the bounded overlay model (visible set + overflow summary). */
export function buildIncidentOverlayModel(
  incidents: readonly IncidentSummary[],
  maxVisible: number = MAX_VISIBLE_INCIDENTS,
): IncidentOverlayModel {
  const active = dedupeIncidents(incidents);
  const cap = Math.max(0, maxVisible);
  return {
    visible: active.slice(0, cap),
    overflowCount: Math.max(0, active.length - cap),
    total: active.length,
  };
}

/** All deduped active incidents targeting a given node id (for per-node badges). */
export function incidentsForTarget(
  incidents: readonly IncidentSummary[],
  nodeId: string,
): IncidentViewModel[] {
  return dedupeIncidents(incidents).filter((vm) => vm.target === nodeId);
}
