import { describe, expect, it } from 'vitest';
import {
  resolveNodeVisualStatus,
  statusAppearance,
  nodeStatusAppearance,
} from '../../src/game/nodeStatus';

describe('resolveNodeVisualStatus', () => {
  it('load_balancer with no health → not_applicable (NOT Healthy)', () => {
    const s = resolveNodeVisualStatus({ kind: 'load_balancer', enabled: true });
    expect(s).toEqual({ kind: 'not_applicable' });
    const a = statusAppearance(s);
    expect(a.toneKey).toBe('NotApplicable');
    expect(a.shortText).toBe('Health N/A');
    expect(a.color).not.toBe(0x1e9e57); // not the Healthy green
    expect(a.glyph).toBe('—');
  });

  it('app_server with missing health → not_reported (NOT Healthy)', () => {
    const s = resolveNodeVisualStatus({ kind: 'app_server', enabled: true });
    expect(s).toEqual({ kind: 'not_reported' });
    const a = statusAppearance(s);
    expect(a.toneKey).toBe('NotReported');
    expect(a.shortText).toBe('Status unavailable');
    expect(a.glyph).toBe('?');
    expect(a.color).not.toBe(0x1e9e57);
  });

  it('explicit Healthy stays Healthy (green)', () => {
    const s = resolveNodeVisualStatus({ kind: 'app_server', enabled: true, health: 'Healthy' });
    expect(s).toEqual({ kind: 'health', health: 'Healthy' });
    expect(statusAppearance(s).toneKey).toBe('Healthy');
  });

  it('reported Warning/Critical/Down keep their tone', () => {
    for (const h of ['Warning', 'Critical', 'Down'] as const) {
      const a = nodeStatusAppearance({ kind: 'redis', enabled: true, health: h });
      expect(a.toneKey).toBe(h);
    }
  });

  it('disabled takes precedence and is never Healthy', () => {
    const withHealth = resolveNodeVisualStatus({ kind: 'app_server', enabled: false, health: 'Healthy' });
    expect(withHealth).toEqual({ kind: 'disabled' });
    const noHealth = resolveNodeVisualStatus({ kind: 'load_balancer', enabled: false });
    expect(noHealth).toEqual({ kind: 'disabled' });
    expect(statusAppearance(withHealth).toneKey).toBe('Disabled');
  });

  it('an unknown health enum value → not_reported (no Healthy fallback)', () => {
    const s = resolveNodeVisualStatus({ kind: 'app_server', enabled: true, health: 'Melting' });
    expect(s).toEqual({ kind: 'not_reported' });
  });

  it('unknown node kind with missing health → not_reported', () => {
    const s = resolveNodeVisualStatus({ kind: 'quantum_db', enabled: true });
    expect(s).toEqual({ kind: 'not_reported' });
  });

  it('never produces an undefined colour (no crash surface)', () => {
    for (const input of [
      { kind: 'load_balancer', enabled: true },
      { kind: 'app_server', enabled: true },
      { kind: 'app_server', enabled: false, health: 'Critical' as const },
      { kind: 'mystery', enabled: true, health: 'weird' },
    ]) {
      const a = nodeStatusAppearance(input);
      expect(typeof a.color).toBe('number');
      expect(typeof a.border).toBe('number');
    }
  });
});
