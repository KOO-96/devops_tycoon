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

export type AssetLoadState = 'idle' | 'loading' | 'ready' | 'failed';
