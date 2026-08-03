import { describe, expect, it } from 'vitest';

import {
  incidentKey,
  dedupeIncidents,
  buildIncidentOverlayModel,
  incidentsForTarget,
  MAX_VISIBLE_INCIDENTS,
} from '../../src/game/incidentModel';
import type { IncidentSummary } from '../../src/api/schemas';

const inc = (type: string, target: string, phase: string): IncidentSummary => ({ type, target, phase });

describe('incident overlay model (POLICY-C-FU-003)', () => {
  it('builds a stable type:target key', () => {
    expect(incidentKey({ type: 'APP_CPU_OVERLOAD', target: 'app-1' })).toBe('APP_CPU_OVERLOAD:app-1');
    expect(incidentKey({ type: null, target: null })).toBe('incident:system');
  });

  it('dedupes duplicate (type,target) rows into one', () => {
    const out = dedupeIncidents([
      inc('APP_CPU_OVERLOAD', 'app-1', 'ACTIVE'),
      inc('APP_CPU_OVERLOAD', 'app-1', 'ACTIVE'),
    ]);
    expect(out).toHaveLength(1);
  });

  it('keeps the highest-priority phase for a key', () => {
    const out = dedupeIncidents([
      inc('DB_CPU_SATURATION', 'db-1', 'WARNING'),
      inc('DB_CPU_SATURATION', 'db-1', 'ACTIVE'),
    ]);
    expect(out[0]?.phase).toBe('ACTIVE');
  });

  it('removes RECOVERED incidents (never left active)', () => {
    const out = dedupeIncidents([inc('CACHE_MISS_SPIKE', 'redis-1', 'RECOVERED')]);
    expect(out).toHaveLength(0);
  });

  it('sorts deterministically by phase then type then target', () => {
    const out = dedupeIncidents([
      inc('REQUEST_TIMEOUT', 'z', 'WARNING'),
      inc('APP_CPU_OVERLOAD', 'a', 'ACTIVE'),
      inc('APP_MEM_SATURATION', 'b', 'ACTIVE'),
    ]);
    expect(out.map((v) => v.type)).toEqual(['APP_CPU_OVERLOAD', 'APP_MEM_SATURATION', 'REQUEST_TIMEOUT']);
  });

  it('bounds the visible set and reports overflow', () => {
    const many: IncidentSummary[] = Array.from({ length: MAX_VISIBLE_INCIDENTS + 3 }, (_, i) =>
      inc('APP_CPU_OVERLOAD', `app-${i}`, 'ACTIVE'),
    );
    const model = buildIncidentOverlayModel(many);
    expect(model.visible).toHaveLength(MAX_VISIBLE_INCIDENTS);
    expect(model.overflowCount).toBe(3);
    expect(model.total).toBe(MAX_VISIBLE_INCIDENTS + 3);
  });

  it('filters incidents for a specific target node', () => {
    const list = [
      inc('LB_IMBALANCE', 'lb-1', 'ACTIVE'),
      inc('APP_CPU_OVERLOAD', 'app-1', 'ACTIVE'),
    ];
    expect(incidentsForTarget(list, 'lb-1').map((v) => v.type)).toEqual(['LB_IMBALANCE']);
    expect(incidentsForTarget(list, 'nope')).toHaveLength(0);
  });

  it('treats an unknown/absent phase as ACTIVE (never dropped or invented)', () => {
    const out = dedupeIncidents([{ type: 'NO_HEALTHY_SERVER', target: 'lb-1', phase: null }]);
    expect(out[0]?.phase).toBe('ACTIVE');
  });
});
