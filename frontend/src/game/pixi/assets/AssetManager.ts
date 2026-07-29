/**
 * Asset Manager skeleton (§19–§20). Owns the manifest, shared/generated textures,
 * and load state; hands out asset handles to the scene. In PR B no final atlas is
 * loaded — only a generated fallback texture and the missing-asset flow exist.
 *
 * Ownership boundary (§20): the AssetManager owns SHARED + generated-fallback
 * textures and the manifest; the Scene owns Sprites/Graphics/Containers/listeners.
 * The scene must NOT blanket-destroy the manager's textures. FE-ART-003 (final
 * shared-atlas lifecycle) is NOT complete — this only lays the ownership seam.
 */

import type { Texture } from 'pixi.js';
import type { AssetLoadState, AssetManifest, AssetManifestEntry } from './assetTypes';
import { validateManifest, type ManifestProblem } from './assetManifest';
import { createFallbackTexture, fallbackSpec } from './generatedFallback';

export interface AssetHandle {
  assetId: string;
  /** Resolved texture, or null → caller draws a Graphics placeholder. */
  texture: Texture | null;
  isFallback: boolean;
}

let warnedOnce = false; // throttle dev-log spam across the app

export class AssetManager {
  private byId = new Map<string, AssetManifestEntry>();
  private state: AssetLoadState = 'idle';
  private fallbackTexture: Texture | null = null;
  private problems: ManifestProblem[] = [];
  private disposed = false;

  /** Register (and validate) a manifest. Invalid manifests do not throw. */
  registerManifest(manifest: AssetManifest): ManifestProblem[] {
    this.problems = validateManifest(manifest);
    if (this.problems.length > 0 && import.meta.env?.DEV && !warnedOnce) {
      warnedOnce = true;
      // eslint-disable-next-line no-console
      console.warn('[AssetManager] manifest problems:', this.problems);
    }
    // Only index valid, unique entries; ignore the rest (fallbacks cover them).
    this.byId = new Map();
    for (const e of manifest.assets) {
      if (e.assetId && !this.byId.has(e.assetId)) this.byId.set(e.assetId, e);
    }
    return this.problems;
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

  /**
   * Preload (PR B: no real images, so this just resolves the generated fallback
   * and marks ready). Idempotent — repeated calls do not reload.
   */
  preload(): Promise<void> {
    if (this.disposed || this.state === 'ready' || this.state === 'loading') return Promise.resolve();
    this.state = 'loading';
    try {
      this.ensureFallback();
      this.state = 'ready';
    } catch {
      this.state = 'failed';
    }
    return Promise.resolve();
  }

  /** Resolve an asset to a handle; unknown/missing ids yield the fallback. */
  resolve(assetId: string | undefined): AssetHandle {
    const entry = assetId ? this.byId.get(assetId) : undefined;
    if (!entry) {
      return { assetId: assetId ?? 'fallback', texture: this.ensureFallback(), isFallback: true };
    }
    // PR B: no real textures are loaded yet → everything resolves to fallback.
    return { assetId: entry.assetId, texture: this.ensureFallback(), isFallback: true };
  }

  /** The shared generated fallback texture (created once, owned by the manager). */
  private ensureFallback(): Texture | null {
    if (this.fallbackTexture) return this.fallbackTexture;
    this.fallbackTexture = createFallbackTexture(fallbackSpec());
    return this.fallbackTexture;
  }

  /** Release manager-owned textures (call when the manager is truly done). */
  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    try {
      this.fallbackTexture?.destroy(true);
    } catch {
      /* already gone */
    }
    this.fallbackTexture = null;
    this.byId.clear();
    this.state = 'idle';
  }
}
