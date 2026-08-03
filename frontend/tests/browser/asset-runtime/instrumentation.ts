/** Test-page-only instrumentation. Never exposed on the production app global. */

import type { AssetManager } from '../../../src/game/pixi/assets/AssetManager';
import type { ControlledAssetLoader, LoaderCallRecord } from './controlledAssetLoader';

export interface AssetRuntimeDebugSnapshot {
  cacheEntries: number;
  refCounts: Record<string, number>;
  loaderCalls: LoaderCallRecord[];
  textureCreates: number;
  textureDestroys: number;
}

export function snapshot(
  manager: AssetManager,
  loader: ControlledAssetLoader,
  assetIds: readonly string[],
): AssetRuntimeDebugSnapshot {
  const refCounts: Record<string, number> = {};
  for (const id of assetIds) refCounts[id] = manager.refCountOf(id);
  return {
    cacheEntries: manager.cacheSize(),
    refCounts,
    loaderCalls: loader.calls.map((c) => ({ ...c })),
    textureCreates: loader.textureCreates,
    textureDestroys: loader.textureDestroys,
  };
}
