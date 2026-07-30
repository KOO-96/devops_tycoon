/**
 * Application-scoped Asset Runtime (FE-ART-003: FU-001..004). Owns shared textures,
 * the generated fallback, the manifest registry, a VERSIONED cache, and load
 * lifecycle. Hands out reference-counted `AssetHandle`s. ONE instance per runtime,
 * created at bootstrap and injected into scenes; a scene NEVER disposes it.
 *
 * Guarantees:
 *  - same assetId@assetVersion → same Texture (one upload); concurrent acquires
 *    share one load promise.
 *  - `release()` decrements a refCount and does NOT eagerly destroy; a texture is
 *    freed only by `disposeStale()` (refCount 0) or `disposeAll()`.
 *  - a new asset version never silently overwrites a version an existing scene is
 *    using (cache key includes the version).
 *  - a load that completes after dispose is discarded and its texture destroyed —
 *    never registered into a disposed manager.
 *  - a missing/failed asset resolves down a bounded fallback chain (depth ≤ 3, no
 *    cycles); the terminal generated fallback never fails.
 *
 * NO blanket `destroy({ texture: true })`, NO per-route disposal. Backward-compatible
 * legacy API (`registerManifest`/`getState`/`resolve`/`preload()`/`dispose()`) is
 * retained for existing callers/tests.
 */

import type { Texture } from 'pixi.js';
import type { AssetCacheState, AssetLoadState, AssetManifest, AssetManifestEntry } from './assetTypes';
import { validateManifest, type ManifestProblem } from './assetManifest';
import { createFallbackTexture, fallbackSpec } from './generatedFallback';
import {
  buildDevelopmentManifest,
  UNIVERSAL_FALLBACK_ASSET_ID,
} from './generatedBuildingAsset';
import { AssetLoadError, GeneratedAssetLoader, type AssetLoader } from './assetLoader';
import { runWithRetry, type RetryPolicy, type SleepFn } from './retry';

export const MAX_FALLBACK_DEPTH = 3;

export interface AssetHandle {
  readonly assetId: string;
  readonly assetVersion: string;
  readonly texture: Texture | null;
  /** Legacy name (kept). True when the texture is a fallback, not the requested art. */
  readonly isFallback: boolean;
  /** FE-ART-003 name (same meaning as isFallback). */
  readonly fallback: boolean;
  readonly released: boolean;
  release(): void;
}

export interface AcquireOptions {
  signal?: AbortSignal;
}

export interface PreloadResult {
  ready: number;
  failed: number;
}

export interface AssetManagerOptions {
  loader?: AssetLoader;
  sleep?: SleepFn;
  retryPolicy?: Partial<RetryPolicy>;
  /** Register the generated development manifest on construction (default true). */
  registerDevelopmentManifest?: boolean;
}

interface CacheEntry {
  key: string;
  assetId: string;
  assetVersion: string;
  state: AssetCacheState;
  texture: Texture | null;
  loadPromise: Promise<Texture> | null;
  refCount: number;
  stale: boolean;
  fallback: boolean;
  lastError: AssetLoadError | null;
  abort: AbortController | null;
}

let warnedOnce = false; // throttle dev-log spam across the app

function cacheKey(assetId: string, version: string): string {
  return `${assetId}@${version}`;
}

export class AssetManager {
  private byId = new Map<string, AssetManifestEntry>();
  private cache = new Map<string, CacheEntry>();
  private manifestVersion = '0';
  private state: AssetLoadState = 'idle';
  private fallbackTexture: Texture | null = null;
  private problems: ManifestProblem[] = [];
  private disposed = false;
  private readonly loader: AssetLoader;
  private readonly sleep: SleepFn | undefined;
  private readonly retryPolicy: Partial<RetryPolicy> | undefined;
  private readonly lifecycle = new AbortController(); // aborts on disposeAll

  constructor(options: AssetManagerOptions = {}) {
    this.loader = options.loader ?? new GeneratedAssetLoader();
    this.sleep = options.sleep;
    this.retryPolicy = options.retryPolicy;
    if (options.registerDevelopmentManifest !== false) {
      this.registerManifest(buildDevelopmentManifest());
    }
  }

  // --- manifest registry ----------------------------------------------------

  /** Register (validate) a manifest, replacing the registry index. Invalid
   * manifests do not throw; blocking problems leave the previous registry intact. */
  registerManifest(manifest: AssetManifest): ManifestProblem[] {
    this.problems = validateManifest(manifest);
    if (this.problems.length > 0 && import.meta.env?.DEV && !warnedOnce) {
      warnedOnce = true;
      // eslint-disable-next-line no-console
      console.warn('[AssetManager] manifest problems:', this.problems);
    }
    if (this.hasBlockingProblems(this.problems)) return this.problems;
    this.byId = new Map();
    for (const e of manifest.assets) {
      if (e.assetId && !this.byId.has(e.assetId)) this.byId.set(e.assetId, e);
    }
    this.manifestVersion = manifest.manifestVersion || '0';
    return this.problems;
  }

  /**
   * Replace the manifest (versioned). New/changed entries are registered; cache
   * entries for versions no longer current are marked STALE (existing handles keep
   * working until released). On a blocking-invalid manifest the current manifest is
   * kept unchanged. Returns validation problems.
   */
  replaceManifest(manifest: AssetManifest): ManifestProblem[] {
    if (this.disposed) return [];
    const problems = validateManifest(manifest);
    if (this.hasBlockingProblems(problems)) {
      this.problems = problems;
      return problems; // keep the last good manifest
    }
    const next = new Map<string, AssetManifestEntry>();
    for (const e of manifest.assets) {
      if (e.assetId && !next.has(e.assetId)) next.set(e.assetId, e);
    }
    const nextVersion = manifest.manifestVersion || '0';
    // Mark cache entries stale when their version is no longer the current one.
    for (const ce of this.cache.values()) {
      const entry = next.get(ce.assetId);
      const currentVersion = entry ? this.entryVersion(entry, nextVersion) : undefined;
      if (currentVersion === undefined || currentVersion !== ce.assetVersion) {
        ce.stale = true;
        if (ce.state === 'ready') ce.state = 'stale';
      }
    }
    this.byId = next;
    this.manifestVersion = nextVersion;
    this.problems = problems;
    this.disposeStale();
    return problems;
  }

  getManifestProblems(): ManifestProblem[] {
    return this.problems;
  }

  getState(): AssetLoadState {
    return this.state;
  }

  getEntry(assetId: string): AssetManifestEntry | undefined {
    return this.byId.get(assetId);
  }

  /** Test/inspection helper: number of live cache entries. */
  cacheSize(): number {
    return this.cache.size;
  }

  /** Test/inspection helper: refCount for an asset id at its current version. */
  refCountOf(assetId: string): number {
    const entry = this.byId.get(assetId);
    const version = entry ? this.entryVersion(entry, this.manifestVersion) : this.manifestVersion;
    return this.cache.get(cacheKey(assetId, version))?.refCount ?? 0;
  }

  // --- preload / legacy resolve ---------------------------------------------

  /** Warm the fallback (+ optional asset ids) without holding references. Idempotent
   * for the no-arg legacy call (marks ready). */
  async preload(ids?: readonly string[]): Promise<PreloadResult> {
    if (this.disposed) return { ready: 0, failed: 0 };
    if (this.state !== 'ready') this.state = 'loading';
    this.ensureFallback();
    let ready = 0;
    let failed = 0;
    for (const id of ids ?? []) {
      const handle = await this.acquire(id);
      if (handle.texture && !handle.fallback) ready++;
      else failed++;
      handle.release(); // preload does not retain a reference
    }
    this.state = 'ready';
    return { ready, failed };
  }

  /** Legacy synchronous resolve → always the shared fallback handle (detached,
   * refCount-free). Retained for pre-PR-C callers/tests. */
  resolve(assetId: string | undefined): AssetHandle {
    const texture = this.disposed ? null : this.ensureFallback();
    return this.detachedFallbackHandle(assetId ?? 'fallback', texture);
  }

  // --- acquire / release (refcounted, versioned) ----------------------------

  async acquire(assetId: string, options: AcquireOptions = {}): Promise<AssetHandle> {
    if (this.disposed) return this.detachedFallbackHandle(assetId, null);
    const resolved = await this.acquireEntry(assetId, new Set<string>(), options.signal);
    if (this.disposed) {
      // Disposed mid-load: do not hand out a live reference.
      return this.detachedFallbackHandle(assetId, null);
    }
    resolved.entry.refCount += 1;
    return this.makeHandle(resolved.entry, resolved.fallback);
  }

  private async acquireEntry(
    assetId: string,
    chain: Set<string>,
    signal: AbortSignal | undefined,
  ): Promise<{ entry: CacheEntry; fallback: boolean }> {
    // Depth / cycle guard → terminal generated fallback (never fails).
    if (chain.has(assetId) || chain.size >= MAX_FALLBACK_DEPTH) {
      return { entry: this.terminalFallbackEntry(), fallback: true };
    }
    const manifestEntry = this.byId.get(assetId);
    if (!manifestEntry) {
      // Unknown id → jump straight to the universal fallback (bounded).
      if (assetId === UNIVERSAL_FALLBACK_ASSET_ID) {
        return { entry: this.terminalFallbackEntry(), fallback: true };
      }
      chain.add(assetId);
      return this.acquireEntry(UNIVERSAL_FALLBACK_ASSET_ID, chain, signal);
    }
    const version = this.entryVersion(manifestEntry, this.manifestVersion);
    const ce = this.ensureCacheEntry(assetId, version);
    try {
      await this.ensureLoaded(ce, manifestEntry, signal);
      return { entry: ce, fallback: ce.fallback };
    } catch (err) {
      ce.lastError = err instanceof AssetLoadError ? err : new AssetLoadError('unknown', String(err));
      // Aborted by manager dispose → stop; caller returns a detached fallback.
      if (this.disposed || this.lifecycle.signal.aborted) {
        return { entry: this.terminalFallbackEntry(), fallback: true };
      }
      const next = manifestEntry.fallbackAssetId ?? (assetId !== UNIVERSAL_FALLBACK_ASSET_ID ? UNIVERSAL_FALLBACK_ASSET_ID : null);
      if (!next || chain.has(next)) {
        return { entry: this.terminalFallbackEntry(), fallback: true };
      }
      chain.add(assetId);
      const res = await this.acquireEntry(next, chain, signal);
      return { entry: res.entry, fallback: true };
    }
  }

  private ensureLoaded(
    ce: CacheEntry,
    manifestEntry: AssetManifestEntry,
    signal: AbortSignal | undefined,
  ): Promise<Texture> {
    if (ce.state === 'ready' && ce.texture) return Promise.resolve(ce.texture);
    if (ce.loadPromise) return ce.loadPromise;

    ce.state = 'loading';
    ce.abort = new AbortController();
    const combined = this.combineSignals([this.lifecycle.signal, ce.abort.signal, signal]);
    const promise = runWithRetry<Texture>({
      ...(this.retryPolicy ? { policy: this.retryPolicy } : {}),
      ...(this.sleep ? { sleep: this.sleep } : {}),
      signal: combined,
      attempt: (ctx) => this.loader.load(manifestEntry, { signal: ctx.signal, attempt: ctx.attempt }),
    })
      .then((texture) => {
        if (this.disposed) {
          // Completed after dispose → discard; never register into a dead manager.
          try {
            texture.destroy(true);
          } catch {
            /* already gone */
          }
          throw new AssetLoadError('aborted', 'manager disposed during load', { retryable: false });
        }
        ce.texture = texture;
        ce.state = ce.stale ? 'stale' : 'ready';
        ce.loadPromise = null;
        return texture;
      })
      .catch((err: unknown) => {
        ce.state = 'failed';
        ce.loadPromise = null;
        throw err;
      });
    ce.loadPromise = promise;
    return promise;
  }

  private ensureCacheEntry(assetId: string, version: string): CacheEntry {
    const key = cacheKey(assetId, version);
    let ce = this.cache.get(key);
    if (!ce) {
      ce = {
        key,
        assetId,
        assetVersion: version,
        state: 'idle',
        texture: null,
        loadPromise: null,
        refCount: 0,
        stale: false,
        fallback: assetId === UNIVERSAL_FALLBACK_ASSET_ID,
        lastError: null,
        abort: null,
      };
      this.cache.set(key, ce);
    }
    return ce;
  }

  /** The terminal generated fallback as a cache entry (its texture never fails). */
  private terminalFallbackEntry(): CacheEntry {
    const ce = this.ensureCacheEntry(UNIVERSAL_FALLBACK_ASSET_ID, this.manifestVersion);
    ce.fallback = true;
    if (!ce.texture) {
      ce.texture = this.ensureFallback();
      ce.state = ce.texture ? 'ready' : 'failed';
    }
    return ce;
  }

  private makeHandle(ce: CacheEntry, fallback: boolean): AssetHandle {
    let released = false;
    const release = (): void => {
      if (released) return; // double release is a safe no-op
      released = true;
      if (ce.refCount > 0) ce.refCount -= 1;
      this.maybeCollect(ce);
    };
    return {
      assetId: ce.assetId,
      assetVersion: ce.assetVersion,
      texture: ce.texture,
      isFallback: fallback,
      fallback,
      get released(): boolean {
        return released;
      },
      release,
    };
  }

  private detachedFallbackHandle(assetId: string, texture: Texture | null): AssetHandle {
    return {
      assetId,
      assetVersion: '0',
      texture,
      isFallback: true,
      fallback: true,
      released: true,
      release(): void {
        /* detached: nothing to release */
      },
    };
  }

  // --- disposal -------------------------------------------------------------

  /** Free STALE cache entries whose refCount has reached 0. */
  disposeStale(): void {
    for (const [key, ce] of this.cache) {
      if (ce.stale && ce.refCount <= 0) {
        this.destroyEntry(ce);
        this.cache.delete(key);
      }
    }
  }

  private maybeCollect(ce: CacheEntry): void {
    if (ce.stale && ce.refCount <= 0) {
      this.destroyEntry(ce);
      this.cache.delete(ce.key);
    }
  }

  /** Reset for HMR: dispose textures/loads but keep the instance usable. Dev-only
   * path; production must not call this. */
  async resetForHmr(): Promise<void> {
    await this.disposeAll();
    this.disposed = false;
    this.state = 'idle';
    this.registerManifest(buildDevelopmentManifest());
  }

  /** Full teardown: abort pending loads, block new registration of results, destroy
   * every owned texture. Idempotent. Legacy `dispose()` aliases this. */
  async disposeAll(): Promise<void> {
    if (this.disposed) return;
    this.disposed = true;
    this.lifecycle.abort(new AssetLoadError('aborted', 'manager disposed', { retryable: false }));
    // Let any in-flight loads settle so their post-dispose branch destroys textures.
    const pending = [...this.cache.values()].map((ce) => ce.loadPromise).filter(Boolean) as Promise<Texture>[];
    await Promise.allSettled(pending);
    for (const ce of this.cache.values()) this.destroyEntry(ce);
    this.cache.clear();
    try {
      this.fallbackTexture?.destroy(true);
    } catch {
      /* already gone */
    }
    this.fallbackTexture = null;
    this.byId.clear();
    this.state = 'idle';
  }

  /** Legacy synchronous dispose (idempotent). Prefer `disposeAll()`. */
  dispose(): void {
    void this.disposeAll();
  }

  // --- internals ------------------------------------------------------------

  private destroyEntry(ce: CacheEntry): void {
    ce.abort?.abort();
    if (ce.texture && ce.texture !== this.fallbackTexture) {
      try {
        ce.texture.destroy(true);
      } catch {
        /* already gone */
      }
    }
    ce.texture = null;
    ce.loadPromise = null;
    ce.state = 'disposed';
  }

  private ensureFallback(): Texture | null {
    if (this.disposed) return null;
    if (this.fallbackTexture) return this.fallbackTexture;
    this.fallbackTexture = createFallbackTexture(fallbackSpec());
    return this.fallbackTexture;
  }

  private entryVersion(entry: AssetManifestEntry, manifestVersion: string): string {
    return entry.assetVersion ?? manifestVersion ?? '0';
  }

  private hasBlockingProblems(problems: ManifestProblem[]): boolean {
    // A duplicate-id or fallback-cycle is structurally unsafe → block replacement.
    return problems.some((p) => p.code === 'DUP_ID' || p.code === 'FALLBACK_CYCLE');
  }

  private combineSignals(signals: Array<AbortSignal | undefined>): AbortSignal {
    const present = signals.filter((s): s is AbortSignal => s !== undefined);
    const ac = new AbortController();
    for (const s of present) {
      if (s.aborted) {
        ac.abort(s.reason);
        return ac.signal;
      }
      s.addEventListener('abort', () => ac.abort(s.reason), { once: true });
    }
    return ac.signal;
  }
}
