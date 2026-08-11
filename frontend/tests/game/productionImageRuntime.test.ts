/**
 * ProductionImageAssetLoader through the AssetManager (P3A §25/§26 runtime paths):
 * checksum comparison, single integrity refetch, fallback, concurrency, dispose races,
 * and version isolation — all owned by the AssetManager, with the real image loader.
 */

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

vi.mock('pixi.js', async () => await import('../helpers/fakePixi'));

import type { Texture as PixiTexture } from 'pixi.js';
import { Texture } from '../helpers/fakePixi';
import { AssetManager } from '../../src/game/pixi/assets/AssetManager';
import { WebCryptoChecksumVerifier } from '../../src/game/pixi/assets/assetLoader';
import { ProductionImageAssetLoader } from '../../src/game/pixi/assets/productionImageLoader';
import type { AssetManifest, AssetManifestEntry } from '../../src/game/pixi/assets/assetTypes';

const BYTES = new Uint8Array([9, 8, 7, 6, 5, 4, 3, 2, 1, 0]);
const fakeTex = (): PixiTexture => Texture.from() as unknown as PixiTexture;
const backoffOnly = (ms: number): Promise<void> =>
  ms >= 1000 ? new Promise<void>(() => {}) : Promise.resolve();

let GOOD = '';
beforeAll(async () => {
  GOOD = await new WebCryptoChecksumVerifier().sha256(BYTES);
});

const managers: AssetManager[] = [];
afterEach(async () => {
  while (managers.length) await managers.pop()!.disposeAll();
});

function imgEntry(checksum: string, version = '1'): AssetManifestEntry {
  return {
    assetId: 'building.a.primary',
    assetVersion: version,
    category: 'building',
    sourceType: 'image',
    source: 'https://cdn/a.png',
    checksum,
  };
}
function manifest(entry: AssetManifestEntry): AssetManifest {
  return { manifestVersion: entry.assetVersion ?? '1', assets: [entry], categoryFallbacks: {} };
}

function okResponse(): Response {
  return new Response(BYTES as unknown as BodyInit, { status: 200, headers: { 'content-type': 'image/png' } });
}

function makeManager(fetchImpl: typeof fetch, m: AssetManifest): AssetManager {
  const loader = new ProductionImageAssetLoader({ fetchImpl, decode: async () => fakeTex() });
  const mgr = new AssetManager({ loader, sleep: backoffOnly, registerDevelopmentManifest: false });
  mgr.registerManifest(m);
  managers.push(mgr);
  return mgr;
}

describe('production image loading via AssetManager', () => {
  it('loads a matching-checksum image as the primary (not a fallback)', async () => {
    const mgr = makeManager(vi.fn(async () => okResponse()) as unknown as typeof fetch, manifest(imgEntry(GOOD)));
    const h = await mgr.acquire('building.a.primary');
    expect(h.fallback).toBe(false);
    expect(h.texture).toBeTruthy();
    expect(mgr.lastTierOf('building.a.primary')).toBe('primary');
    h.release();
  });

  it('on a checksum mismatch: one integrity refetch, then fallback (fetch twice)', async () => {
    const fetchImpl = vi.fn(async () => okResponse());
    const mgr = makeManager(fetchImpl as unknown as typeof fetch, manifest(imgEntry('c'.repeat(64))));
    const h = await mgr.acquire('building.a.primary');
    expect(h.fallback).toBe(true); // corrupt → falls back to the universal terminal
    expect(fetchImpl).toHaveBeenCalledTimes(2); // normal + one integrity refetch
    const secondCall = fetchImpl.mock.calls[1] as unknown[] | undefined;
    expect(secondCall?.[1]).toMatchObject({ cache: 'no-store' });
    h.release();
  });

  it('shares one load across concurrent acquires (single fetch)', async () => {
    const fetchImpl = vi.fn(async () => okResponse());
    const mgr = makeManager(fetchImpl as unknown as typeof fetch, manifest(imgEntry(GOOD)));
    const [h1, h2] = await Promise.all([mgr.acquire('building.a.primary'), mgr.acquire('building.a.primary')]);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(h1.texture).toBe(h2.texture);
    h1.release();
    h2.release();
  });

  it('is safe when disposed during an in-flight fetch', async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    const fetchImpl = vi.fn(async () => {
      await gate;
      return okResponse();
    });
    const mgr = makeManager(fetchImpl as unknown as typeof fetch, manifest(imgEntry(GOOD)));
    const acquiring = mgr.acquire('building.a.primary');
    const disposing = mgr.disposeAll(); // dispose while the fetch is pending
    release(); // let the fetch settle so dispose's allSettled can complete
    await disposing;
    const h = await acquiring;
    expect(h.fallback).toBe(true); // disposed mid-load → detached fallback handle
  });

  it('isolates cache entries across asset versions', async () => {
    const fetchImpl = vi.fn(async () => okResponse());
    const mgr = makeManager(fetchImpl as unknown as typeof fetch, manifest(imgEntry(GOOD, '1')));
    const h1 = await mgr.acquire('building.a.primary');
    mgr.replaceManifest(manifest(imgEntry(GOOD, '2')));
    const h2 = await mgr.acquire('building.a.primary');
    expect(h1.assetVersion).toBe('1');
    expect(h2.assetVersion).toBe('2');
    h1.release();
    h2.release();
  });
});

// ---- P3A targeted follow-up coverage (§8-§11) -----------------------------

function respFrom(bytes: Uint8Array, status = 200): Response {
  const init: ResponseInit = status === 200 ? { status, headers: { 'content-type': 'image/png' } } : { status };
  return new Response(bytes as unknown as BodyInit, init);
}
function seqFetch(responses: Response[]): ReturnType<typeof vi.fn> {
  let i = 0;
  return vi.fn(async () => responses[Math.min(i++, responses.length - 1)]);
}
function trackingDecode(): { decode: () => Promise<PixiTexture>; textures: PixiTexture[] } {
  const textures: PixiTexture[] = [];
  const decode = async (): Promise<PixiTexture> => {
    const t = { destroy: vi.fn() } as unknown as PixiTexture;
    textures.push(t);
    return t;
  };
  return { decode, textures };
}
function managerWith(loader: ProductionImageAssetLoader, m: AssetManifest): AssetManager {
  const mgr = new AssetManager({ loader, sleep: backoffOnly, registerDevelopmentManifest: false });
  mgr.registerManifest(m);
  managers.push(mgr);
  return mgr;
}

describe('production image loader — targeted follow-up paths', () => {
  it('integrity refetch SUCCESS: first bytes corrupt, refetch good → primary; corrupt texture destroyed', async () => {
    const fetchImpl = seqFetch([respFrom(new Uint8Array([1, 1, 1, 1])), respFrom(BYTES)]);
    const { decode, textures } = trackingDecode();
    const loader = new ProductionImageAssetLoader({ fetchImpl: fetchImpl as unknown as typeof fetch, decode });
    const mgr = managerWith(loader, manifest(imgEntry(GOOD))); // entry.checksum = sha256(BYTES)
    const h = await mgr.acquire('building.a.primary');
    expect(h.fallback).toBe(false);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    expect((fetchImpl.mock.calls[1] as unknown[])?.[1]).toMatchObject({ cache: 'no-store' });
    expect(textures[0]!.destroy).toHaveBeenCalled(); // corrupt texture destroyed
    expect(textures[1]!.destroy).not.toHaveBeenCalled(); // good texture kept
    h.release();
  });

  it('503 → transient retry → 200 success (no integrity refetch)', async () => {
    const fetchImpl = seqFetch([respFrom(new Uint8Array(), 503), respFrom(BYTES)]);
    const { decode, textures } = trackingDecode();
    const loader = new ProductionImageAssetLoader({ fetchImpl: fetchImpl as unknown as typeof fetch, decode });
    const mgr = managerWith(loader, manifest(imgEntry(GOOD)));
    const h = await mgr.acquire('building.a.primary');
    expect(h.fallback).toBe(false);
    expect(fetchImpl).toHaveBeenCalledTimes(2); // 503 + 200 (transient retry, not integrity refetch)
    expect(textures.length).toBe(1); // 503 never reaches decode
    expect(mgr.lastTierOf('building.a.primary')).toBe('primary');
    h.release();
  });

  it('double mismatch: both corrupt textures destroyed, then fallback', async () => {
    const fetchImpl = seqFetch([respFrom(new Uint8Array([1])), respFrom(new Uint8Array([2]))]);
    const { decode, textures } = trackingDecode();
    const loader = new ProductionImageAssetLoader({ fetchImpl: fetchImpl as unknown as typeof fetch, decode });
    const mgr = managerWith(loader, manifest(imgEntry(GOOD)));
    const h = await mgr.acquire('building.a.primary');
    expect(h.fallback).toBe(true);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    expect(textures.length).toBe(2);
    expect(textures[0]!.destroy).toHaveBeenCalled();
    expect(textures[1]!.destroy).toHaveBeenCalled();
    h.release();
  });

  it('is safe when disposed during decode: late texture destroyed, not registered', async () => {
    let releaseDecode!: () => void;
    const gate = new Promise<void>((r) => (releaseDecode = r));
    const textures: PixiTexture[] = [];
    const decode = async (): Promise<PixiTexture> => {
      await gate;
      const t = { destroy: vi.fn() } as unknown as PixiTexture;
      textures.push(t);
      return t;
    };
    const loader = new ProductionImageAssetLoader({
      fetchImpl: vi.fn(async () => okResponse()) as unknown as typeof fetch,
      decode,
    });
    const mgr = managerWith(loader, manifest(imgEntry(GOOD)));
    const acquiring = mgr.acquire('building.a.primary');
    const disposing = mgr.disposeAll();
    releaseDecode(); // let decode finish AFTER dispose began
    const h = await acquiring;
    await disposing;
    expect(h.fallback).toBe(true);
    expect(textures.length).toBe(1);
    expect(textures[0]!.destroy).toHaveBeenCalled(); // discarded, never registered into a disposed manager
  });

  it('swap peak (FU-008 lifecycle): v1+v2 textures coexist, then v1 is cleaned up (no double-destroy)', async () => {
    const { decode, textures } = trackingDecode();
    const fetchImpl = vi.fn(async () => okResponse()); // GOOD bytes → primary both versions
    const loader = new ProductionImageAssetLoader({ fetchImpl: fetchImpl as unknown as typeof fetch, decode });
    const mgr = managerWith(loader, manifest(imgEntry(GOOD, '1')));

    const hA = await mgr.acquire('building.a.primary'); // v1 → textures[0]
    mgr.replaceManifest(manifest(imgEntry(GOOD, '2'))); // v1 marked stale (hA still held)
    const hB = await mgr.acquire('building.a.primary'); // v2 → textures[1]

    // PEAK: both version textures are resident simultaneously.
    expect(textures.length).toBe(2);
    expect(hA.assetVersion).toBe('1');
    expect(hB.assetVersion).toBe('2');
    expect(textures[0]!.destroy).not.toHaveBeenCalled();
    expect(textures[1]!.destroy).not.toHaveBeenCalled();

    // Release v1 → stale cleanup destroys ONLY texture A (no double-destroy); v2 remains.
    hA.release();
    expect(textures[0]!.destroy).toHaveBeenCalledTimes(1);
    expect(textures[1]!.destroy).not.toHaveBeenCalled();
    hB.release();
  });
});
