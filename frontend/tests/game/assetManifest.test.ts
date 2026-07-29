import { describe, expect, it } from 'vitest';
import { isManifestValid, validateManifest } from '../../src/game/pixi/assets/assetManifest';
import type { AssetManifest } from '../../src/game/pixi/assets/assetTypes';

const base = (assets: AssetManifest['assets']): AssetManifest => ({ manifestVersion: '1.0.0', assets });

describe('manifest validation', () => {
  it('accepts a valid manifest', () => {
    const m = base([
      { assetId: 'gen-fallback', category: 'fallback', sourceType: 'generated' },
      { assetId: 'b-app', category: 'building', sourceType: 'generated', footprint: { width: 1, height: 1 }, fallbackAssetId: 'gen-fallback' },
    ]);
    expect(isManifestValid(m)).toBe(true);
  });

  it('flags missing manifestVersion', () => {
    const m = { manifestVersion: '', assets: [] } as AssetManifest;
    expect(validateManifest(m).some((p) => p.code === 'NO_VERSION')).toBe(true);
  });

  it('flags duplicate assetId', () => {
    const m = base([
      { assetId: 'x', category: 'building', sourceType: 'generated' },
      { assetId: 'x', category: 'tile', sourceType: 'generated' },
    ]);
    expect(validateManifest(m).some((p) => p.code === 'DUP_ID')).toBe(true);
  });

  it('flags invalid category and sourceType', () => {
    const m = base([{ assetId: 'x', category: 'bogus' as never, sourceType: 'nope' as never }]);
    const codes = validateManifest(m).map((p) => p.code);
    expect(codes).toContain('BAD_CATEGORY');
    expect(codes).toContain('BAD_SOURCE_TYPE');
  });

  it('requires source for image/atlas and frame for atlas', () => {
    const m = base([
      { assetId: 'img', category: 'building', sourceType: 'image' },
      { assetId: 'atl', category: 'building', sourceType: 'atlas', source: 's.json' },
    ]);
    const codes = validateManifest(m).map((p) => p.code);
    expect(codes).toContain('MISSING_SOURCE');
    expect(codes).toContain('MISSING_FRAME');
  });

  it('validates anchor 0..1 and footprint 1..4', () => {
    const m = base([
      { assetId: 'a', category: 'building', sourceType: 'generated', anchor: { x: 2, y: 0 } },
      { assetId: 'f', category: 'building', sourceType: 'generated', footprint: { width: 9, height: 1 } },
    ]);
    const codes = validateManifest(m).map((p) => p.code);
    expect(codes).toContain('BAD_ANCHOR');
    expect(codes).toContain('BAD_FOOTPRINT');
  });

  it('detects a missing fallbackAssetId', () => {
    const m = base([{ assetId: 'a', category: 'building', sourceType: 'generated', fallbackAssetId: 'ghost' }]);
    expect(validateManifest(m).some((p) => p.code === 'MISSING_FALLBACK')).toBe(true);
  });

  it('detects a fallback cycle', () => {
    const m = base([
      { assetId: 'a', category: 'building', sourceType: 'generated', fallbackAssetId: 'b' },
      { assetId: 'b', category: 'building', sourceType: 'generated', fallbackAssetId: 'a' },
    ]);
    expect(validateManifest(m).some((p) => p.code === 'FALLBACK_CYCLE')).toBe(true);
  });
});
