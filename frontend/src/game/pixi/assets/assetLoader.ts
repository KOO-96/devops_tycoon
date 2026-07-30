/**
 * Loader abstraction + error classification + checksum boundary (FE-ART-003
 * §Loader/§Retry, POLICY-C-FU-004/005). Defines the seam a real image/atlas loader
 * will implement, the error taxonomy that decides what may be retried, and the
 * checksum verifier used to enforce binary integrity. The GeneratedAssetLoader used
 * in this PR builds DEVELOPMENT textures from a canvas — no final binary/atlas.
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
  | 'checksum_mismatch'
  | 'missing_asset'
  | 'aborted'
  | 'unknown';

/** Only genuinely transient failures retry. Everything else is terminal. Note that
 * `checksum_mismatch` is NOT retryable here — it is handled by a separate, bounded
 * single integrity refetch in the AssetManager, not by the transient retry loop. */
const RETRYABLE_KINDS: ReadonlySet<AssetErrorKind> = new Set<AssetErrorKind>([
  'network',
  'timeout',
  'server',
]);

export interface AssetLoadErrorInfo {
  assetId?: string;
  assetVersion?: string;
  attemptKind?: AssetLoadMode;
  /** Expected/actual checksums are kept for diagnostics only — never shown to users. */
  expectedChecksum?: string;
  actualChecksum?: string;
}

export class AssetLoadError extends Error {
  readonly kind: AssetErrorKind;
  readonly retryable: boolean;
  readonly info: AssetLoadErrorInfo;
  constructor(kind: AssetErrorKind, message: string, opts?: { retryable?: boolean; info?: AssetLoadErrorInfo }) {
    super(message);
    this.name = 'AssetLoadError';
    this.kind = kind;
    this.retryable = opts?.retryable ?? RETRYABLE_KINDS.has(kind);
    this.info = opts?.info ?? {};
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

export type AssetLoadMode = 'normal' | 'integrity_refetch';

export interface AssetLoadContext {
  signal: AbortSignal;
  attempt: number;
  /** `integrity_refetch` is the single, bounded post-checksum-mismatch re-request. */
  mode: AssetLoadMode;
  /** True during an integrity refetch → the loader must bypass any browser cache so
   * the same corrupt binary is not re-served. */
  bypassCache: boolean;
}

/** Result of a load. A real loader returns the computed checksum (or the bytes it
 * hashed); generated development assets omit it (nothing to verify). */
export interface LoadedAsset {
  texture: Texture;
  computedChecksum?: string;
}

export interface AssetLoader {
  load(entry: AssetManifestEntry, ctx: AssetLoadContext): Promise<LoadedAsset>;
}

// --- checksum boundary (§11) ----------------------------------------------

export interface ChecksumVerifier {
  sha256(bytes: Uint8Array): Promise<string>;
}

/** Normalize a hex checksum for comparison: trim, lower-case, strip a `sha256:`
 * prefix. Comparison is case-insensitive and prefix-insensitive. */
export function normalizeChecksum(value: string): string {
  return value.trim().toLowerCase().replace(/^sha256:/, '');
}

/** True when a string is a well-formed 64-char hex SHA-256 (after normalization). */
export function isValidChecksum(value: string): boolean {
  return /^[a-f0-9]{64}$/.test(normalizeChecksum(value));
}

/** Web Crypto SHA-256 verifier (real loader use). Returns lowercase hex. */
export class WebCryptoChecksumVerifier implements ChecksumVerifier {
  async sha256(bytes: Uint8Array): Promise<string> {
    const subtle = globalThis.crypto?.subtle;
    if (!subtle) throw new AssetLoadError('checksum_mismatch', 'no SubtleCrypto available', { retryable: false });
    const digest = await subtle.digest('SHA-256', bytes as unknown as ArrayBuffer);
    return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
  }
}

/**
 * Builds DEVELOPMENT placeholder textures from generated canvas geometry. Honors the
 * abort signal so dispose/route races are exercised, but performs no network I/O and
 * returns no checksum (generated assets are not integrity-checked).
 */
export class GeneratedAssetLoader implements AssetLoader {
  load(entry: AssetManifestEntry, ctx: AssetLoadContext): Promise<LoadedAsset> {
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
      return Promise.resolve({ texture });
    } catch (err) {
      if (err instanceof AssetLoadError) return Promise.reject(err);
      return Promise.reject(new AssetLoadError('decode', String(err), { retryable: false }));
    }
  }
}
