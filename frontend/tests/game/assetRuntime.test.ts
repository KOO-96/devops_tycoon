import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('pixi.js', async () => await import('../helpers/fakePixi'));

import type { Texture as PixiTexture } from 'pixi.js';
import { Texture } from '../helpers/fakePixi';
import { AssetManager, type AssetHandle } from '../../src/game/pixi/assets/AssetManager';
import { AssetLoadError, type AssetLoader, type AssetLoadContext } from '../../src/game/pixi/assets/assetLoader';
import type { AssetManifestEntry } from '../../src/game/pixi/assets/assetTypes';
import {
  NODE_BUILDING_ASSET_ID,
  UNIVERSAL_FALLBACK_ASSET_ID,
  buildDevelopmentManifest,
} from '../../src/game/pixi/assets/generatedBuildingAsset';

/** The fake texture typed as the real Pixi Texture (runtime is the fake). */
const fakeTex = (): PixiTexture => Texture.from() as unknown as PixiTexture;

const backoffOnly = (ms: number): Promise<void> =>
  ms >= 1000 ? new Promise<void>(() => {}) : Promise.resolve();

/** Loader that returns a fresh fake texture, counting loads per assetId. */
class CountingLoader implements AssetLoader {
  loads = new Map<string, number>();
  load(entry: AssetManifestEntry): Promise<PixiTexture> {
    this.loads.set(entry.assetId, (this.loads.get(entry.assetId) ?? 0) + 1);
    return Promise.resolve(fakeTex());
  }
}

/** Loader that fails a configurable number of times before succeeding. */
class FlakyLoader implements AssetLoader {
  calls = 0;
  constructor(private failTimes: number, private err: AssetLoadError) {}
  load(_entry: AssetManifestEntry, _ctx: AssetLoadContext): Promise<PixiTexture> {
    this.calls += 1;
    if (this.calls <= this.failTimes) return Promise.reject(this.err);
    return Promise.resolve(fakeTex());
  }
}

/** Loader that always fails ONE specific assetId; every other id succeeds. Tracks
 * per-id attempt counts to prove retry behavior at a single chain level. */
class TargetedFailLoader implements AssetLoader {
  attempts = new Map<string, number>();
  constructor(private failId: string, private err: AssetLoadError) {}
  load(entry: AssetManifestEntry): Promise<PixiTexture> {
    this.attempts.set(entry.assetId, (this.attempts.get(entry.assetId) ?? 0) + 1);
    if (entry.assetId === this.failId) return Promise.reject(this.err);
    return Promise.resolve(fakeTex());
  }
}

const managers: AssetManager[] = [];
function makeManager(loader?: AssetLoader): AssetManager {
  const m = new AssetManager({
    sleep: backoffOnly,
    ...(loader ? { loader } : {}),
  });
  managers.push(m);
  return m;
}

afterEach(async () => {
  while (managers.length) await managers.pop()!.disposeAll();
});

describe('AssetManager acquire / handle / refCount', () => {
  it('acquire returns a handle with the requested texture (not fallback)', async () => {
    const m = makeManager(new CountingLoader());
    const h = await m.acquire(NODE_BUILDING_ASSET_ID.redis);
    expect(h.texture).not.toBeNull();
    expect(h.fallback).toBe(false);
    h.release();
  });

  it('shares one texture + one load for the same assetId@version', async () => {
    const loader = new CountingLoader();
    const m = makeManager(loader);
    const [a, b] = await Promise.all([
      m.acquire(NODE_BUILDING_ASSET_ID.app_server),
      m.acquire(NODE_BUILDING_ASSET_ID.app_server),
    ]);
    expect(a.texture).toBe(b.texture);
    expect(loader.loads.get(NODE_BUILDING_ASSET_ID.app_server)).toBe(1);
    expect(m.refCountOf(NODE_BUILDING_ASSET_ID.app_server)).toBe(2);
    a.release();
    b.release();
  });

  it('release decrements refCount; double release is a safe no-op', async () => {
    const m = makeManager(new CountingLoader());
    const h = await m.acquire(NODE_BUILDING_ASSET_ID.redis);
    expect(m.refCountOf(NODE_BUILDING_ASSET_ID.redis)).toBe(1);
    h.release();
    expect(m.refCountOf(NODE_BUILDING_ASSET_ID.redis)).toBe(0);
    h.release(); // no throw, no negative
    expect(m.refCountOf(NODE_BUILDING_ASSET_ID.redis)).toBe(0);
    expect(h.released).toBe(true);
  });

  it('does NOT eagerly destroy the texture on release (refCount 0, not stale)', async () => {
    const m = makeManager(new CountingLoader());
    const h = await m.acquire(NODE_BUILDING_ASSET_ID.redis);
    const tex = h.texture as unknown as { destroy: ReturnType<typeof vi.fn> };
    h.release();
    expect(tex.destroy).not.toHaveBeenCalled();
  });
});

describe('AssetManager versioned cache + manifest replacement', () => {
  it('a new version is a distinct cache entry; existing handles keep their texture', async () => {
    const m = makeManager(new CountingLoader());
    const before = await m.acquire(NODE_BUILDING_ASSET_ID.redis);
    const v1Texture = before.texture;

    m.replaceManifest(buildDevelopmentManifest('dev-2'));
    const after = await m.acquire(NODE_BUILDING_ASSET_ID.redis);

    expect(before.texture).toBe(v1Texture); // old handle unchanged
    expect(after.assetVersion).toBe('dev-2');
    expect(after.texture).not.toBe(v1Texture); // new version → new texture
    before.release();
    after.release();
  });

  it('stale entries are collected once their refCount hits 0', async () => {
    const m = makeManager(new CountingLoader());
    const h = await m.acquire(NODE_BUILDING_ASSET_ID.postgresql); // v1
    m.replaceManifest(buildDevelopmentManifest('dev-2')); // v1 entry → stale, still referenced
    const sizeWhileReferenced = m.cacheSize();
    h.release(); // now refCount 0 → collectable
    m.disposeStale();
    expect(m.cacheSize()).toBeLessThan(sizeWhileReferenced);
  });

  it('rollback re-registers the previous version', async () => {
    const m = makeManager(new CountingLoader());
    const a = await m.acquire(NODE_BUILDING_ASSET_ID.redis); // dev-1
    a.release();
    m.replaceManifest(buildDevelopmentManifest('dev-2'));
    m.disposeStale();
    m.replaceManifest(buildDevelopmentManifest('dev-1')); // rollback
    const b = await m.acquire(NODE_BUILDING_ASSET_ID.redis);
    expect(b.assetVersion).toBe('dev-1');
    b.release();
  });

  it('keeps the previous manifest when a replacement is blocking-invalid', async () => {
    const m = makeManager(new CountingLoader());
    const problems = m.replaceManifest({
      manifestVersion: '2',
      assets: [
        { assetId: 'dup', category: 'building', sourceType: 'generated' },
        { assetId: 'dup', category: 'tile', sourceType: 'generated' },
      ],
    });
    expect(problems.some((p) => p.code === 'DUP_ID')).toBe(true);
    // Original dev manifest still resolves.
    const h = await m.acquire(NODE_BUILDING_ASSET_ID.redis);
    expect(h.texture).not.toBeNull();
    h.release();
  });
});

describe('AssetManager fallback chain + retry', () => {
  it('falls back to the universal generated fallback when an asset keeps failing', async () => {
    const loader = new FlakyLoader(99, new AssetLoadError('server', '503'));
    const m = makeManager(loader);
    const h = await m.acquire(NODE_BUILDING_ASSET_ID.redis);
    expect(h.fallback).toBe(true);
    expect(h.texture).not.toBeNull(); // terminal fallback never fails
    h.release();
  });

  it('retries a transient failure then succeeds without fallback', async () => {
    const loader = new FlakyLoader(1, new AssetLoadError('network', 'net'));
    const m = makeManager(loader);
    const h = await m.acquire(NODE_BUILDING_ASSET_ID.app_server);
    expect(h.fallback).toBe(false);
    expect(loader.calls).toBe(2); // 1 fail + 1 success
    h.release();
  });

  it('does not retry a non-retryable error (primary attempted once, then fallback)', async () => {
    const loader = new TargetedFailLoader(NODE_BUILDING_ASSET_ID.redis, new AssetLoadError('client', '4xx'));
    const m = makeManager(loader);
    const h = await m.acquire(NODE_BUILDING_ASSET_ID.redis);
    // The primary failed exactly once (no retry); the chain then used a fallback.
    expect(loader.attempts.get(NODE_BUILDING_ASSET_ID.redis)).toBe(1);
    expect(h.fallback).toBe(true);
    h.release();
  });

  it('unknown asset id resolves to the universal fallback', async () => {
    const m = makeManager(new CountingLoader());
    const h = await m.acquire('totally.unknown.asset');
    expect(h.fallback).toBe(true);
    expect(h.texture).not.toBeNull();
    h.release();
  });
});

describe('AssetManager dispose / race', () => {
  it('acquire after dispose returns a detached fallback handle', async () => {
    const m = makeManager(new CountingLoader());
    await m.disposeAll();
    managers.length = 0; // already disposed
    const h = await m.acquire(NODE_BUILDING_ASSET_ID.redis);
    expect(h.released).toBe(true);
    expect(h.fallback).toBe(true);
  });

  it('a load completing after dispose does not register and destroys its texture', async () => {
    let resolveLoad: (t: PixiTexture) => void = () => {};
    const destroyed = vi.fn();
    const loader: AssetLoader = {
      load: () =>
        new Promise<PixiTexture>((resolve) => {
          resolveLoad = resolve;
        }),
    };
    const m = makeManager(loader);
    const acquiring = m.acquire(NODE_BUILDING_ASSET_ID.redis);
    const disposing = m.disposeAll();
    resolveLoad({ destroy: destroyed } as unknown as PixiTexture); // completes after dispose began
    await Promise.all([acquiring, disposing]);
    managers.length = 0;
    expect(destroyed).toHaveBeenCalled();
    expect(m.cacheSize()).toBe(0);
  });

  it('disposeAll destroys owned textures; fallback texture is freed', async () => {
    const m = makeManager(new CountingLoader());
    const h = await m.acquire(NODE_BUILDING_ASSET_ID.redis);
    const tex = h.texture as unknown as { destroy: ReturnType<typeof vi.fn> };
    await m.disposeAll();
    managers.length = 0;
    expect(tex.destroy).toHaveBeenCalled();
    expect(m.getState()).toBe('idle');
  });

  it('resetForHmr disposes and leaves the manager usable again', async () => {
    const m = makeManager(new CountingLoader());
    const before = await m.acquire(NODE_BUILDING_ASSET_ID.redis);
    before.release();
    await m.resetForHmr();
    const after = await m.acquire(NODE_BUILDING_ASSET_ID.redis);
    expect(after.texture).not.toBeNull();
    after.release();
  });
});

describe('AssetManager legacy API (backward compatible)', () => {
  it('preload() with no args reaches ready and is idempotent', async () => {
    const m = makeManager(new CountingLoader());
    expect(m.getState()).toBe('idle');
    await m.preload();
    await m.preload();
    expect(m.getState()).toBe('ready');
  });

  it('resolve() returns a fallback handle', () => {
    const m = makeManager(new CountingLoader());
    const h: AssetHandle = m.resolve('x');
    expect(h.isFallback).toBe(true);
  });

  it('preload(ids) warms without holding a reference (refCount returns to 0)', async () => {
    const m = makeManager(new CountingLoader());
    const res = await m.preload([NODE_BUILDING_ASSET_ID.redis, UNIVERSAL_FALLBACK_ASSET_ID]);
    expect(res.ready).toBeGreaterThanOrEqual(1);
    expect(m.refCountOf(NODE_BUILDING_ASSET_ID.redis)).toBe(0);
  });
});
