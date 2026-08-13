/**
 * Regression for the ProductionImageAssetLoader ImageBitmap lifetime bug: the default
 * decoder must NOT close the ImageBitmap eagerly (Pixi v8 uploads the source to the GPU
 * lazily on first render — an early close detaches the source and the sprite renders
 * empty). The bitmap is owned by the TextureSource and released exactly once when the
 * source is destroyed (`texture.destroy(true)`), and never double-closed.
 *
 * This exercises the REAL `defaultDecode` (no injected decode) with a fake
 * `createImageBitmap` + the fake Pixi TextureSource event surface, so it verifies the
 * resource-lifetime CONTRACT — not merely that `Texture.from` was called.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('pixi.js', async () => await import('../helpers/fakePixi'));

import { ProductionImageAssetLoader } from '../../src/game/pixi/assets/productionImageLoader';
import type { AssetLoadContext } from '../../src/game/pixi/assets/assetLoader';
import type { AssetManifestEntry } from '../../src/game/pixi/assets/assetTypes';

const BYTES = new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]);

function ctx(): AssetLoadContext {
  return { signal: new AbortController().signal, attempt: 0, mode: 'normal', bypassCache: false };
}
function imageEntry(): AssetManifestEntry {
  return { assetId: 'building.a.primary', assetVersion: '1', category: 'building', sourceType: 'image', source: 'https://cdn/x.png' };
}
function okResponse(): Response {
  return new Response(BYTES as unknown as BodyInit, { status: 200, headers: { 'content-type': 'image/png' } });
}

interface SourceTexture {
  source: { emit: (ev: string) => void };
  destroy: (destroySource?: boolean) => void;
}

describe('ProductionImageAssetLoader — ImageBitmap lifetime (default decode)', () => {
  let close: ReturnType<typeof vi.fn>;
  const original = (globalThis as { createImageBitmap?: unknown }).createImageBitmap;

  beforeEach(() => {
    close = vi.fn();
    (globalThis as { createImageBitmap?: unknown }).createImageBitmap = vi.fn(
      async () => ({ width: 4, height: 4, close }) as unknown as ImageBitmap,
    );
  });
  afterEach(() => {
    (globalThis as { createImageBitmap?: unknown }).createImageBitmap = original;
  });

  it('keeps the bitmap open until the source is destroyed, then closes it exactly once', async () => {
    const loader = new ProductionImageAssetLoader({ fetchImpl: async () => okResponse() }); // no decode → defaultDecode
    const { texture } = (await loader.load(imageEntry(), ctx())) as unknown as { texture: SourceTexture };

    // 1) NOT closed at load time — Pixi uploads lazily on first render.
    expect(close).not.toHaveBeenCalled();

    // 2) closed exactly once when the AssetManager destroys the texture+source.
    texture.destroy(true);
    expect(close).toHaveBeenCalledTimes(1);

    // 3) no double-close if destroy runs again.
    texture.destroy(true);
    expect(close).toHaveBeenCalledTimes(1);
  });

  it('closes the bitmap immediately if Texture.from throws (no owner to release it later)', async () => {
    const pixi = await import('../helpers/fakePixi');
    const spy = vi.spyOn(pixi.Texture, 'from').mockImplementationOnce(() => {
      throw new Error('boom');
    });
    const loader = new ProductionImageAssetLoader({ fetchImpl: async () => okResponse() });
    await expect(loader.load(imageEntry(), ctx())).rejects.toThrow(/texture creation failed/);
    expect(close).toHaveBeenCalledTimes(1);
    spy.mockRestore();
  });
});
