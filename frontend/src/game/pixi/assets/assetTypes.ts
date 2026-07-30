/** Asset manifest types (PR B runtime schema). No final assets are added here. */

export type AssetCategory = 'building' | 'tile' | 'effect' | 'ui' | 'character' | 'fallback';
export type AssetSourceType = 'image' | 'atlas' | 'generated';

export interface AssetManifestEntry {
  assetId: string;
  category: AssetCategory;
  sourceType: AssetSourceType;
  source?: string;
  frame?: string;
  logicalWidth?: number;
  logicalHeight?: number;
  anchor?: { x: number; y: number };
  footprint?: { width: number; height: number };
  fallbackAssetId?: string;
  /**
   * Per-asset content version (FE-ART-003 / manifest policy). Any content change
   * MUST bump this. The runtime cache key is `assetId@assetVersion`, so a new
   * version never silently overwrites the texture an existing scene is using. When
   * absent, the manifest version is used as the asset version.
   */
  assetVersion?: string;
  /** Bundle this asset belongs to (manifest policy). Advisory in this PR. */
  bundleId?: string;
  /** Integrity value — NOT a cache key. Never used in place of assetVersion. */
  checksum?: string;
  /**
   * ASSET-OPS-001 is NOT complete: full provenance/licensing metadata
   * (source/author/license/created_at/…) is a later, separate field set. This
   * bag is only a forward-compatible placeholder — do not treat rights info as
   * finished in PR B.
   */
  metadata?: Record<string, unknown>;
}

export interface AssetManifest {
  manifestVersion: string;
  assets: AssetManifestEntry[];
}

/** Manager-level coarse load state (kept for backward compatibility). */
export type AssetLoadState = 'idle' | 'loading' | 'ready' | 'failed';

/** Per-entry cache lifecycle state (FE-ART-003 §load-state machine). */
export type AssetCacheState = 'idle' | 'loading' | 'ready' | 'failed' | 'stale' | 'disposed';
