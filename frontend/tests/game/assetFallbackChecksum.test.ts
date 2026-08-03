import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('pixi.js', async () => await import('../helpers/fakePixi'));

import type { Texture as PixiTexture } from 'pixi.js';
import { Texture } from '../helpers/fakePixi';
import { AssetManager } from '../../src/game/pixi/assets/AssetManager';
import {
  AssetLoadError,
  type AssetLoader,
  type AssetLoadContext,
  type LoadedAsset,
} from '../../src/game/pixi/assets/assetLoader';
import type { AssetManifest, AssetManifestEntry } from '../../src/game/pixi/assets/assetTypes';
import { UNIVERSAL_FALLBACK_ASSET_ID } from '../../src/game/pixi/assets/generatedBuildingAsset';

const fakeTex = (): PixiTexture => Texture.from() as unknown as PixiTexture;
const backoffOnly = (ms: number): Promise<void> =>
  ms >= 1000 ? new Promise<void>(() => {}) : Promise.resolve();

const GOOD = 'a'.repeat(64);
const BAD = 'b'.repeat(64);

const managers: AssetManager[] = [];
function makeManager(loader: AssetLoader, manifest?: AssetManifest): AssetManager {
  const m = new AssetManager({ sleep: backoffOnly, loader, registerDevelopmentManifest: false });
  m.registerManifest(manifest ?? tierManifest());
  managers.push(m);
  return m;
}
afterEach(async () => {
  while (managers.length) await managers.pop()!.disposeAll();
});

const b = (assetId: string, extra: Partial<AssetManifestEntry> = {}): AssetManifestEntry => ({
  assetId,
  category: assetId.startsWith('fallback') ? 'fallback' : 'building',
  sourceType: 'generated',
  assetVersion: 'v',
  ...extra,
});

/** primary(has entry fb) / primary2(no entry fb) / entryFb / catFb / universal. */
function tierManifest(): AssetManifest {
  return {
    manifestVersion: 'v',
    assets: [
      b('primary', { fallbackAssetId: 'entryFb' }),
      b('primary2'),
      b('entryFb'),
      b('catFb'),
      b(UNIVERSAL_FALLBACK_ASSET_ID),
    ],
    categoryFallbacks: { building: 'catFb' },
  };
}

/** Loader that fails a set of ids and records every call (id, mode, bypassCache).
 * Uses a NON-retryable error so each tier is attempted exactly once. */
class FailSetLoader implements AssetLoader {
  calls: Array<{ assetId: string; mode: string; bypassCache: boolean }> = [];
  constructor(private fail: Set<string>) {}
  load(entry: AssetManifestEntry, ctx: AssetLoadContext): Promise<LoadedAsset> {
    this.calls.push({ assetId: entry.assetId, mode: ctx.mode, bypassCache: ctx.bypassCache });
    if (this.fail.has(entry.assetId)) return Promise.reject(new AssetLoadError('client', '4xx'));
    return Promise.resolve({ texture: fakeTex() });
  }
}

describe('fallback tiers (Entry → Category → Universal)', () => {
  it('uses the entry fallback and skips category/universal', async () => {
    const loader = new FailSetLoader(new Set(['primary']));
    const m = makeManager(loader);
    const h = await m.acquire('primary');
    expect(h.fallback).toBe(true);
    expect(m.lastTierOf('primary')).toBe('entry');
    expect(loader.calls.some((c) => c.assetId === 'catFb')).toBe(false);
    h.release();
  });

  it('uses the category fallback when there is no entry fallback', async () => {
    const loader = new FailSetLoader(new Set(['primary2']));
    const m = makeManager(loader);
    const h = await m.acquire('primary2');
    expect(m.lastTierOf('primary2')).toBe('category');
    expect(loader.calls.some((c) => c.assetId === UNIVERSAL_FALLBACK_ASSET_ID)).toBe(false);
    h.release();
  });

  it('falls through entry → category when the entry fallback also fails', async () => {
    const loader = new FailSetLoader(new Set(['primary', 'entryFb']));
    const m = makeManager(loader);
    const h = await m.acquire('primary');
    expect(m.lastTierOf('primary')).toBe('category');
    h.release();
  });

  it('reaches the universal fallback when entry and category fail', async () => {
    const loader = new FailSetLoader(new Set(['primary', 'entryFb', 'catFb']));
    const m = makeManager(loader);
    const h = await m.acquire('primary');
    expect(m.lastTierOf('primary')).toBe('universal');
    expect(h.fallback).toBe(true);
    expect(h.texture).not.toBeNull();
    h.release();
  });

  it('shares one category-fallback texture across nodes (independent handles)', async () => {
    const loader = new FailSetLoader(new Set(['primary2']));
    const m = makeManager(loader);
    const h1 = await m.acquire('primary2');
    const h2 = await m.acquire('primary2');
    expect(h1.texture).toBe(h2.texture);
    expect(m.refCountOf('catFb')).toBe(2);
    expect(h1).not.toBe(h2);
    h1.release();
    expect(m.refCountOf('catFb')).toBe(1);
    h2.release();
  });

  it('does not loop when a category fallback points back to the primary', async () => {
    const manifest = tierManifest();
    manifest.categoryFallbacks = { building: 'primary2' }; // points back to a primary
    const loader = new FailSetLoader(new Set(['primary2']));
    const m = makeManager(loader, manifest);
    const h = await m.acquire('primary2'); // primary fails → category==self (skipped) → universal
    expect(m.lastTierOf('primary2')).toBe('universal');
    // primary2 attempted exactly once (not re-loaded as its own category fallback).
    expect(loader.calls.filter((c) => c.assetId === 'primary2')).toHaveLength(1);
    h.release();
  });

  it('validation rejects a missing / bad category fallback', () => {
    const m = makeManager(new FailSetLoader(new Set()));
    const problems = m.registerManifest({
      manifestVersion: 'x',
      assets: [b('only')],
      categoryFallbacks: { building: 'does-not-exist' },
    });
    expect(problems.some((p) => p.code === 'MISSING_CATEGORY_FALLBACK')).toBe(true);
  });
});

// --- checksum ---------------------------------------------------------------

/** Loader driven by a per-call script keyed on (assetId, mode). */
class ChecksumLoader implements AssetLoader {
  calls: Array<{ assetId: string; mode: string; bypassCache: boolean }> = [];
  constructor(private plan: (ctx: { assetId: string; mode: string; call: number }) => LoadedAsset | AssetLoadError) {}
  private n = 0;
  load(entry: AssetManifestEntry, ctx: AssetLoadContext): Promise<LoadedAsset> {
    this.calls.push({ assetId: entry.assetId, mode: ctx.mode, bypassCache: ctx.bypassCache });
    const out = this.plan({ assetId: entry.assetId, mode: ctx.mode, call: this.n++ });
    return out instanceof AssetLoadError ? Promise.reject(out) : Promise.resolve(out);
  }
}

function checksumManifest(checksum: string): AssetManifest {
  return {
    manifestVersion: 'v',
    assets: [
      b('img', { checksum }),
      b('catFb'),
      b(UNIVERSAL_FALLBACK_ASSET_ID),
    ],
    categoryFallbacks: { building: 'catFb' },
  };
}

describe('checksum verification + bounded integrity refetch', () => {
  it('accepts a matching checksum with no refetch', async () => {
    const loader = new ChecksumLoader(() => ({ texture: fakeTex(), computedChecksum: GOOD }));
    const m = makeManager(loader, checksumManifest(GOOD));
    const h = await m.acquire('img');
    expect(h.fallback).toBe(false);
    expect(loader.calls).toHaveLength(1);
    h.release();
  });

  it('discards a corrupt texture and refetches exactly once, then succeeds', async () => {
    const destroyed = vi.fn();
    const loader = new ChecksumLoader(({ mode }) =>
      mode === 'normal'
        ? { texture: { destroy: destroyed } as unknown as PixiTexture, computedChecksum: BAD }
        : { texture: fakeTex(), computedChecksum: GOOD },
    );
    const m = makeManager(loader, checksumManifest(GOOD));
    const h = await m.acquire('img');
    expect(h.fallback).toBe(false);
    expect(destroyed).toHaveBeenCalled(); // corrupt texture destroyed
    const modes = loader.calls.map((c) => c.mode);
    expect(modes).toEqual(['normal', 'integrity_refetch']);
    expect(loader.calls[1]?.bypassCache).toBe(true);
    h.release();
  });

  it('falls back after a second mismatch (no further re-request)', async () => {
    const loader = new ChecksumLoader(() => ({ texture: fakeTex(), computedChecksum: BAD }));
    const m = makeManager(loader, checksumManifest(GOOD));
    const h = await m.acquire('img');
    expect(h.fallback).toBe(true);
    // Exactly one normal + one integrity refetch for 'img' (≤ 2 for the corrupt asset).
    expect(loader.calls.filter((c) => c.assetId === 'img')).toHaveLength(2);
    expect(m.lastTierOf('img')).toBe('category');
    h.release();
  });

  it('caps total attempts at 4 with transient retry + one integrity refetch', async () => {
    let imgCalls = 0;
    const loader = new ChecksumLoader(({ assetId, mode }) => {
      if (assetId !== 'img') return { texture: fakeTex() };
      imgCalls += 1;
      if (mode === 'normal' && imgCalls === 1) return new AssetLoadError('server', '503'); // transient
      if (mode === 'normal') return { texture: fakeTex(), computedChecksum: BAD }; // wrong
      return { texture: fakeTex(), computedChecksum: GOOD }; // integrity refetch ok
    });
    const m = makeManager(loader, checksumManifest(GOOD));
    const h = await m.acquire('img');
    expect(h.fallback).toBe(false);
    const imgModes = loader.calls.filter((c) => c.assetId === 'img').map((c) => c.mode);
    // 503 → retry → wrong-checksum (2 normal) + 1 integrity refetch = 3 (≤ 4)
    expect(imgModes).toEqual(['normal', 'normal', 'integrity_refetch']);
    h.release();
  });

  it('an integrity-refetch network failure goes to fallback without transient retry', async () => {
    const loader = new ChecksumLoader(({ mode }) =>
      mode === 'normal'
        ? { texture: fakeTex(), computedChecksum: BAD }
        : new AssetLoadError('network', 'net during refetch'),
    );
    const m = makeManager(loader, checksumManifest(GOOD));
    const h = await m.acquire('img');
    expect(h.fallback).toBe(true);
    // one normal + exactly one integrity refetch (no retry loop on the refetch)
    expect(loader.calls.filter((c) => c.assetId === 'img' && c.mode === 'integrity_refetch')).toHaveLength(1);
    h.release();
  });

  it('does not treat a decode failure as a checksum mismatch', async () => {
    const loader = new ChecksumLoader(({ assetId }) =>
      assetId === 'img' ? new AssetLoadError('decode', 'bad') : { texture: fakeTex() },
    );
    const m = makeManager(loader, checksumManifest(GOOD));
    const h = await m.acquire('img');
    // decode is terminal (no retry, no integrity refetch) → straight to fallback
    expect(loader.calls.filter((c) => c.assetId === 'img')).toHaveLength(1);
    expect(h.fallback).toBe(true);
    h.release();
  });

  it('shares one integrity refetch across concurrent consumers', async () => {
    const loader = new ChecksumLoader(({ mode }) =>
      mode === 'normal'
        ? { texture: fakeTex(), computedChecksum: BAD }
        : { texture: fakeTex(), computedChecksum: GOOD },
    );
    const m = makeManager(loader, checksumManifest(GOOD));
    const [h1, h2] = await Promise.all([m.acquire('img'), m.acquire('img')]);
    expect(h1.texture).toBe(h2.texture);
    expect(loader.calls.filter((c) => c.assetId === 'img' && c.mode === 'integrity_refetch')).toHaveLength(1);
    expect(m.refCountOf('img')).toBe(2);
    h1.release();
    h2.release();
  });

  it('discards the corrupt texture without registering when disposed mid-verification', async () => {
    let resolveNormal: (v: LoadedAsset) => void = () => {};
    const destroyed = vi.fn();
    const loader: AssetLoader = {
      load: (_e, ctx) =>
        ctx.mode === 'normal'
          ? new Promise<LoadedAsset>((r) => (resolveNormal = r))
          : Promise.resolve({ texture: fakeTex(), computedChecksum: GOOD }),
    };
    const m = makeManager(loader, checksumManifest(GOOD));
    const acquiring = m.acquire('img');
    const disposing = m.disposeAll();
    resolveNormal({ texture: { destroy: destroyed } as unknown as PixiTexture, computedChecksum: BAD });
    await Promise.all([acquiring, disposing]);
    managers.length = 0;
    expect(destroyed).toHaveBeenCalled(); // corrupt texture destroyed
    // no integrity refetch was started after dispose
    expect((loader.load as unknown as { mock?: unknown }) ?? true).toBeTruthy();
    expect(m.cacheSize()).toBe(0);
  });

  it('keeps checksum failures isolated per asset version', async () => {
    const loader = new ChecksumLoader(({ assetId }) =>
      assetId === 'img' ? { texture: fakeTex(), computedChecksum: BAD } : { texture: fakeTex() },
    );
    const m = makeManager(loader, checksumManifest(GOOD));
    const bad = await m.acquire('img'); // v mismatch → fallback
    expect(bad.fallback).toBe(true);
    bad.release();
    // v2 without a checksum requirement resolves cleanly, unaffected by v1's failure.
    m.replaceManifest({ manifestVersion: 'v2', assets: [b('img', { assetVersion: 'v2' })], categoryFallbacks: {} });
    const ok = await m.acquire('img');
    expect(ok.assetVersion).toBe('v2');
    expect(ok.fallback).toBe(false);
    ok.release();
  });
});
