/**
 * Production image asset loader + source-type router (Asset Production Enablement P3A).
 *
 * `ProductionImageAssetLoader` fetches `entry.source`, classifies the HTTP result,
 * computes the SHA-256 of the RECEIVED BYTES (Web Crypto), decodes to a Pixi Texture,
 * and returns `{ texture, computedChecksum }`. It does NOT compare checksums or fall
 * back — the AssetManager owns expected-vs-computed comparison, the single bounded
 * integrity refetch, the attempt cap, and fallback (see AssetManager.loadAndVerify).
 *
 * `RoutingAssetLoader` dispatches by `entry.sourceType`:
 *   generated → GeneratedAssetLoader (development canvas textures)
 *   image     → ProductionImageAssetLoader
 *   atlas     → explicit `unsupported` error (BLOCKED_BY_P3B) — never silently generated.
 *
 * The frontend consumes only the generated Runtime Manifest; it never re-derives
 * approval/inclusion/mapping/build_id (those live in the Python generator + canonical.py).
 */

import { Texture } from 'pixi.js';
import type { AssetManifestEntry } from './assetTypes';
import {
  AssetLoadError,
  classifyHttpStatus,
  WebCryptoChecksumVerifier,
  type AssetLoadContext,
  type AssetLoader,
  type ChecksumVerifier,
  type LoadedAsset,
} from './assetLoader';

/** Decode received bytes into a Texture. Injectable so unit tests can avoid real GPU. */
export type ImageDecoder = (
  bytes: Uint8Array,
  contentType: string | null,
  signal: AbortSignal,
) => Promise<Texture>;

export interface ProductionImageLoaderDeps {
  fetchImpl?: typeof fetch;
  verifier?: ChecksumVerifier;
  decode?: ImageDecoder;
}

/** Default decoder: createImageBitmap → Texture. Cleans up the bitmap/blob URL. */
async function defaultDecode(
  bytes: Uint8Array,
  contentType: string | null,
  signal: AbortSignal,
): Promise<Texture> {
  if (signal.aborted) throw new AssetLoadError('aborted', 'aborted before decode', { retryable: false });
  const type = contentType && contentType.startsWith('image/') ? contentType : 'image/png';
  const blob = new Blob([bytes as unknown as BlobPart], { type });
  if (typeof createImageBitmap === 'function') {
    let bitmap: ImageBitmap | null = null;
    try {
      bitmap = await createImageBitmap(blob);
      const texture = Texture.from(bitmap);
      return texture;
    } catch (err) {
      throw new AssetLoadError('decode', `image decode failed: ${String(err)}`, { retryable: false });
    } finally {
      bitmap?.close?.();
    }
  }
  // Fallback path (no createImageBitmap): HTMLImageElement + object URL.
  if (typeof document === 'undefined' || typeof URL?.createObjectURL !== 'function') {
    throw new AssetLoadError('decode', 'no image decode facility available', { retryable: false });
  }
  const url = URL.createObjectURL(blob);
  try {
    const img = await loadHtmlImage(url, signal);
    return Texture.from(img);
  } finally {
    URL.revokeObjectURL(url);
  }
}

function loadHtmlImage(url: string, signal: AbortSignal): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const onAbort = (): void => reject(new AssetLoadError('aborted', 'aborted during decode', { retryable: false }));
    if (signal.aborted) return onAbort();
    signal.addEventListener('abort', onAbort, { once: true });
    img.onload = (): void => resolve(img);
    img.onerror = (): void => reject(new AssetLoadError('decode', 'HTMLImage decode failed', { retryable: false }));
    img.src = url;
  });
}

export class ProductionImageAssetLoader implements AssetLoader {
  private readonly fetchImpl: typeof fetch;
  private readonly verifier: ChecksumVerifier;
  private readonly decode: ImageDecoder;

  constructor(deps: ProductionImageLoaderDeps = {}) {
    this.fetchImpl = deps.fetchImpl ?? ((...a: Parameters<typeof fetch>) => fetch(...a));
    this.verifier = deps.verifier ?? new WebCryptoChecksumVerifier();
    this.decode = deps.decode ?? defaultDecode;
  }

  async load(entry: AssetManifestEntry, ctx: AssetLoadContext): Promise<LoadedAsset> {
    if (ctx.signal.aborted) {
      throw new AssetLoadError('aborted', 'aborted before fetch', { retryable: false });
    }
    if (!entry.source) {
      throw new AssetLoadError('schema', `image entry ${entry.assetId} has no source`, {
        retryable: false,
        info: { assetId: entry.assetId },
      });
    }

    let response: Response;
    try {
      response = await this.fetchImpl(entry.source, {
        signal: ctx.signal,
        // integrity refetch must bypass the browser cache so corrupt bytes aren't re-served.
        cache: ctx.bypassCache ? 'no-store' : 'default',
      });
    } catch (err) {
      if (isAbortError(err)) {
        throw new AssetLoadError('aborted', 'fetch aborted', { retryable: false });
      }
      throw new AssetLoadError('network', `fetch failed: ${String(err)}`, {
        retryable: true,
        info: { assetId: entry.assetId },
      });
    }

    if (!response.ok) {
      const kind = classifyHttpStatus(response.status);
      throw new AssetLoadError(kind, `HTTP ${response.status} for ${entry.assetId}`, {
        info: { assetId: entry.assetId },
      });
    }

    const contentType = response.headers.get('content-type');
    if (contentType && !contentType.startsWith('image/')) {
      throw new AssetLoadError('decode', `non-image content-type '${contentType}'`, {
        retryable: false,
        info: { assetId: entry.assetId },
      });
    }

    const bytes = new Uint8Array(await response.arrayBuffer());
    const computedChecksum = await this.verifier.sha256(bytes);
    const texture = await this.decode(bytes, contentType, ctx.signal);
    return { texture, computedChecksum };
  }
}

function isAbortError(err: unknown): boolean {
  return (
    err instanceof AssetLoadError
      ? err.kind === 'aborted'
      : typeof err === 'object' && err !== null && (err as { name?: string }).name === 'AbortError'
  );
}

export class RoutingAssetLoader implements AssetLoader {
  constructor(
    private readonly generated: AssetLoader,
    private readonly image: AssetLoader,
  ) {}

  load(entry: AssetManifestEntry, ctx: AssetLoadContext): Promise<LoadedAsset> {
    switch (entry.sourceType) {
      case 'generated':
        return this.generated.load(entry, ctx);
      case 'image':
        return this.image.load(entry, ctx);
      case 'atlas':
        return Promise.reject(
          new AssetLoadError('unsupported', `atlas source not supported in P3A (BLOCKED_BY_P3B): ${entry.assetId}`, {
            retryable: false,
            info: { assetId: entry.assetId },
          }),
        );
      default:
        return Promise.reject(
          new AssetLoadError('unsupported', `unsupported sourceType '${String(entry.sourceType)}'`, {
            retryable: false,
            info: { assetId: entry.assetId },
          }),
        );
    }
  }
}
