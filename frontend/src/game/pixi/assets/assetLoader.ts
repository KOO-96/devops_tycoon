/**
 * Loader abstraction + error classification (FE-ART-003 §Loader, §Retry). Defines
 * the seam a real image/atlas loader will implement later, plus the error taxonomy
 * that decides what may be retried. The GeneratedAssetLoader used in this PR builds
 * DEVELOPMENT textures from a canvas — no final binary/atlas is loaded.
 */

import { Texture } from 'pixi.js';
import type { AssetManifestEntry } from './assetTypes';
import { drawBuildingAsset, buildingAssetSpec } from './generatedBuildingAsset';

export type AssetErrorKind =
  | 'network'
  | 'timeout'
  | 'server' // transient 5xx
  | 'not_found' // 404
  | 'client' // other 4xx
  | 'schema'
  | 'manifest'
  | 'license'
  | 'approval'
  | 'decode'
  | 'checksum'
  | 'missing_asset'
  | 'aborted'
  | 'unknown';

/** Only genuinely transient failures retry. Everything else is terminal. */
const RETRYABLE_KINDS: ReadonlySet<AssetErrorKind> = new Set<AssetErrorKind>([
  'network',
  'timeout',
  'server',
]);

export class AssetLoadError extends Error {
  readonly kind: AssetErrorKind;
  readonly retryable: boolean;
  constructor(kind: AssetErrorKind, message: string, opts?: { retryable?: boolean }) {
    super(message);
    this.name = 'AssetLoadError';
    this.kind = kind;
    this.retryable = opts?.retryable ?? RETRYABLE_KINDS.has(kind);
  }
}

export function isRetryableError(err: unknown): boolean {
  return err instanceof AssetLoadError ? err.retryable : false;
}

/** Classify an HTTP status into an error kind (used by a future real loader). */
export function classifyHttpStatus(status: number): AssetErrorKind {
  if (status === 404) return 'not_found';
  if (status >= 400 && status < 500) return 'client';
  if (status >= 500) return 'server';
  return 'unknown';
}

export interface AssetLoadContext {
  signal: AbortSignal;
  attempt: number;
}

export interface AssetLoader {
  load(entry: AssetManifestEntry, ctx: AssetLoadContext): Promise<Texture>;
}

/**
 * Builds DEVELOPMENT placeholder textures from generated canvas geometry. Used in
 * place of a real image/atlas loader for this PR. Honors the abort signal (throws
 * an aborted error if the load is cancelled mid-flight) so dispose/route races are
 * exercised by tests, but never performs network I/O.
 */
export class GeneratedAssetLoader implements AssetLoader {
  load(entry: AssetManifestEntry, ctx: AssetLoadContext): Promise<Texture> {
    if (ctx.signal.aborted) {
      return Promise.reject(new AssetLoadError('aborted', 'load aborted before start', { retryable: false }));
    }
    try {
      const spec = buildingAssetSpec(entry.assetId);
      if (typeof document === 'undefined') {
        throw new AssetLoadError('decode', 'no document to draw a canvas', { retryable: false });
      }
      const canvas = document.createElement('canvas');
      drawBuildingAsset(canvas, spec);
      const texture = Texture.from(canvas);
      if (!texture) throw new AssetLoadError('decode', 'texture creation failed', { retryable: false });
      return Promise.resolve(texture);
    } catch (err) {
      if (err instanceof AssetLoadError) return Promise.reject(err);
      return Promise.reject(new AssetLoadError('decode', String(err), { retryable: false }));
    }
  }
}
