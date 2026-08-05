/**
 * ProductionImageAssetLoader + RoutingAssetLoader unit tests (P3A §25).
 * Fetch and decode are injected so these run in jsdom without a real GPU; the real
 * createImageBitmap/Texture path is exercised by the browser harness (§27).
 */

import { describe, it, expect, vi } from 'vitest';
import type { Texture } from 'pixi.js';
import type { AssetManifestEntry } from '../../src/game/pixi/assets/assetTypes';
import {
  AssetLoadError,
  WebCryptoChecksumVerifier,
  type AssetLoadContext,
} from '../../src/game/pixi/assets/assetLoader';
import { GeneratedAssetLoader } from '../../src/game/pixi/assets/assetLoader';
import {
  ProductionImageAssetLoader,
  RoutingAssetLoader,
} from '../../src/game/pixi/assets/productionImageLoader';

const BYTES = new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]);
const fakeTexture = (): Texture => ({ destroy: () => {} }) as unknown as Texture;
const fakeDecode = async (): Promise<Texture> => fakeTexture();

function ctx(overrides: Partial<AssetLoadContext> = {}): AssetLoadContext {
  return {
    signal: new AbortController().signal,
    attempt: 0,
    mode: 'normal',
    bypassCache: false,
    ...overrides,
  };
}

function imageEntry(source = 'https://cdn/x.png'): AssetManifestEntry {
  return { assetId: 'building.a.primary', assetVersion: '1', category: 'building', sourceType: 'image', source };
}

function okResponse(bytes: Uint8Array, contentType = 'image/png'): Response {
  return new Response(bytes as unknown as BodyInit, { status: 200, headers: { 'content-type': contentType } });
}

async function expectedChecksum(): Promise<string> {
  return new WebCryptoChecksumVerifier().sha256(BYTES);
}

describe('ProductionImageAssetLoader', () => {
  it('fetches, computes SHA-256 of received bytes, and decodes a texture', async () => {
    const loader = new ProductionImageAssetLoader({
      fetchImpl: async () => okResponse(BYTES),
      decode: fakeDecode,
    });
    const result = await loader.load(imageEntry(), ctx());
    expect(result.texture).toBeTruthy();
    expect(result.computedChecksum).toBe(await expectedChecksum());
  });

  it('does NOT compare against the expected checksum (Manager owns comparison)', async () => {
    // Even with a mismatching entry.checksum, the loader just returns the computed one.
    const loader = new ProductionImageAssetLoader({ fetchImpl: async () => okResponse(BYTES), decode: fakeDecode });
    const entry = { ...imageEntry(), checksum: 'deadbeef'.repeat(8) };
    const result = await loader.load(entry, ctx());
    expect(result.computedChecksum).toBe(await expectedChecksum());
  });

  it('classifies HTTP 404 as terminal not_found', async () => {
    const loader = new ProductionImageAssetLoader({ fetchImpl: async () => new Response(null, { status: 404 }), decode: fakeDecode });
    await expect(loader.load(imageEntry(), ctx())).rejects.toMatchObject({ kind: 'not_found', retryable: false });
  });

  it('classifies HTTP 503 as transient server', async () => {
    const loader = new ProductionImageAssetLoader({ fetchImpl: async () => new Response(null, { status: 503 }), decode: fakeDecode });
    await expect(loader.load(imageEntry(), ctx())).rejects.toMatchObject({ kind: 'server', retryable: true });
  });

  it('classifies a thrown fetch (network) as transient', async () => {
    const loader = new ProductionImageAssetLoader({
      fetchImpl: async () => {
        throw new TypeError('network down');
      },
      decode: fakeDecode,
    });
    await expect(loader.load(imageEntry(), ctx())).rejects.toMatchObject({ kind: 'network', retryable: true });
  });

  it('propagates a decode failure as terminal', async () => {
    const loader = new ProductionImageAssetLoader({
      fetchImpl: async () => okResponse(BYTES),
      decode: async () => {
        throw new AssetLoadError('decode', 'boom', { retryable: false });
      },
    });
    await expect(loader.load(imageEntry(), ctx())).rejects.toMatchObject({ kind: 'decode' });
  });

  it('rejects a non-image content-type', async () => {
    const loader = new ProductionImageAssetLoader({ fetchImpl: async () => okResponse(BYTES, 'text/html'), decode: fakeDecode });
    await expect(loader.load(imageEntry(), ctx())).rejects.toMatchObject({ kind: 'decode' });
  });

  it('honors a pre-aborted signal', async () => {
    const ac = new AbortController();
    ac.abort();
    const loader = new ProductionImageAssetLoader({ fetchImpl: async () => okResponse(BYTES), decode: fakeDecode });
    await expect(loader.load(imageEntry(), ctx({ signal: ac.signal }))).rejects.toMatchObject({ kind: 'aborted' });
  });

  it('bypasses the browser cache on an integrity refetch', async () => {
    const fetchImpl = vi.fn(async () => okResponse(BYTES));
    const loader = new ProductionImageAssetLoader({ fetchImpl: fetchImpl as unknown as typeof fetch, decode: fakeDecode });
    await loader.load(imageEntry(), ctx({ mode: 'integrity_refetch', bypassCache: true }));
    expect(fetchImpl).toHaveBeenCalledWith('https://cdn/x.png', expect.objectContaining({ cache: 'no-store' }));
  });

  it('rejects an entry with no source', async () => {
    const loader = new ProductionImageAssetLoader({ fetchImpl: async () => okResponse(BYTES), decode: fakeDecode });
    const noSource: AssetManifestEntry = { assetId: 'building.a.primary', assetVersion: '1', category: 'building', sourceType: 'image' };
    await expect(loader.load(noSource, ctx())).rejects.toMatchObject({ kind: 'schema' });
  });
});

describe('RoutingAssetLoader', () => {
  it('routes image → image loader and generated → generated loader', async () => {
    const image = new ProductionImageAssetLoader({ fetchImpl: async () => okResponse(BYTES), decode: fakeDecode });
    const imageSpy = vi.spyOn(image, 'load');
    const generated = new GeneratedAssetLoader();
    const genSpy = vi.spyOn(generated, 'load').mockResolvedValue({ texture: fakeTexture() });
    const router = new RoutingAssetLoader(generated, image);

    await router.load(imageEntry(), ctx());
    expect(imageSpy).toHaveBeenCalledOnce();

    await router.load({ assetId: 'fallback.x', category: 'fallback', sourceType: 'generated' }, ctx());
    expect(genSpy).toHaveBeenCalledOnce();
  });

  it('rejects atlas with an explicit unsupported error (never silently generated)', async () => {
    const generated = new GeneratedAssetLoader();
    const genSpy = vi.spyOn(generated, 'load');
    const router = new RoutingAssetLoader(generated, new ProductionImageAssetLoader());
    await expect(
      router.load({ assetId: 'ui.badge', category: 'ui', sourceType: 'atlas', source: 'a.json', frame: 'f' }, ctx()),
    ).rejects.toMatchObject({ kind: 'unsupported', retryable: false });
    expect(genSpy).not.toHaveBeenCalled();
  });
});
