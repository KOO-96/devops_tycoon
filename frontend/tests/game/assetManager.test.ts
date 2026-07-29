import { describe, expect, it, vi } from 'vitest';

vi.mock('pixi.js', async () => await import('../helpers/fakePixi'));

import { AssetManager } from '../../src/game/pixi/assets/AssetManager';
import { fallbackSpec, drawFallback } from '../../src/game/pixi/assets/generatedFallback';
import type { AssetManifest } from '../../src/game/pixi/assets/assetTypes';

describe('AssetManager', () => {
  it('preloads to ready and reports idle→ready', async () => {
    const m = new AssetManager();
    expect(m.getState()).toBe('idle');
    await m.preload();
    expect(m.getState()).toBe('ready');
  });

  it('resolves an unknown asset id to a fallback handle', () => {
    const m = new AssetManager();
    const h = m.resolve('does-not-exist');
    expect(h.isFallback).toBe(true);
  });

  it('registers a manifest and surfaces problems without throwing', () => {
    const m = new AssetManager();
    const bad: AssetManifest = {
      manifestVersion: '1.0.0',
      assets: [
        { assetId: 'dup', category: 'building', sourceType: 'generated' },
        { assetId: 'dup', category: 'tile', sourceType: 'generated' },
      ],
    };
    const problems = m.registerManifest(bad);
    expect(problems.some((p) => p.code === 'DUP_ID')).toBe(true);
  });

  it('preload is idempotent', async () => {
    const m = new AssetManager();
    await m.preload();
    await m.preload();
    expect(m.getState()).toBe('ready');
  });

  it('dispose is safe and resets state', () => {
    const m = new AssetManager();
    m.dispose();
    m.dispose(); // idempotent
    expect(m.getState()).toBe('idle');
  });
});

describe('generated fallback spec', () => {
  it('has an UNKNOWN label and a "?" glyph (non-colour cue)', () => {
    const s = fallbackSpec();
    expect(s.glyph).toBe('?');
    expect(s.label).toBe('UNKNOWN');
  });

  it('drawFallback does not throw when a 2d context is unavailable (jsdom)', () => {
    const canvas = document.createElement('canvas');
    expect(() => drawFallback(canvas, fallbackSpec())).not.toThrow();
  });
});
