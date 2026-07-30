import { describe, expect, it } from 'vitest';

import {
  clientLocalDescriptor,
  clientConnectionDescriptor,
  clientSyncDescriptor,
  assetRuntimeDescriptor,
  nodeStatusSourceClass,
  nodeStatusDescriptor,
} from '../../src/game/visualSource';
import { resolveNodeVisualStatus } from '../../src/game/nodeStatus';

describe('Client Runtime Source Classes (POLICY-C-FU-001)', () => {
  it('classifies selection as CLIENT_LOCAL, not a health source', () => {
    expect(clientLocalDescriptor('Selected').sourceClass).toBe('CLIENT_LOCAL');
    expect(clientLocalDescriptor('Unselected').sourceClass).toBe('CLIENT_LOCAL');
  });

  it('classifies reconnecting as CLIENT_CONNECTION', () => {
    expect(clientConnectionDescriptor('Reconnecting').sourceClass).toBe('CLIENT_CONNECTION');
    expect(clientConnectionDescriptor('Disconnected').sourceClass).toBe('CLIENT_CONNECTION');
  });

  it('classifies snapshot sync failure as CLIENT_SYNC', () => {
    expect(clientSyncDescriptor('SnapshotSyncFailed').sourceClass).toBe('CLIENT_SYNC');
  });

  it('classifies asset fallback as ASSET_RUNTIME', () => {
    expect(assetRuntimeDescriptor('FallbackActive').sourceClass).toBe('ASSET_RUNTIME');
    expect(assetRuntimeDescriptor('AssetUnavailable').sourceClass).toBe('ASSET_RUNTIME');
  });

  it('maps operational health to HEALTH_ENUM', () => {
    const s = resolveNodeVisualStatus({ kind: 'app_server', enabled: true, health: 'Warning' });
    expect(nodeStatusSourceClass(s)).toBe('HEALTH_ENUM');
    expect(nodeStatusDescriptor(s).tone).toBe('Warning');
  });

  it('maps disabled to ENABLED_FIELD', () => {
    const s = resolveNodeVisualStatus({ kind: 'app_server', enabled: false });
    expect(nodeStatusSourceClass(s)).toBe('ENABLED_FIELD');
  });

  it('maps N/A and unavailable to CAPABILITY_DERIVED (never a client class)', () => {
    const na = resolveNodeVisualStatus({ kind: 'load_balancer', enabled: true });
    const unrep = resolveNodeVisualStatus({ kind: 'app_server', enabled: true });
    expect(nodeStatusSourceClass(na)).toBe('CAPABILITY_DERIVED');
    expect(nodeStatusSourceClass(unrep)).toBe('CAPABILITY_DERIVED');
  });

  it('never classifies a node health as a client-local/connection/sync source', () => {
    for (const health of ['Healthy', 'Warning', 'Critical', 'Down'] as const) {
      const s = resolveNodeVisualStatus({ kind: 'redis', enabled: true, health });
      const cls = nodeStatusSourceClass(s);
      expect(['CLIENT_LOCAL', 'CLIENT_CONNECTION', 'CLIENT_SYNC', 'ASSET_RUNTIME']).not.toContain(cls);
    }
  });
});
