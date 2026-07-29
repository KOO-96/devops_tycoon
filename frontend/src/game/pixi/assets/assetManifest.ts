/**
 * Manifest validation (§18). Pure and unit-tested. Returns a list of problems
 * rather than throwing, so callers can decide (dev = surface, prod = fallback).
 */

import type { AssetCategory, AssetManifest, AssetManifestEntry, AssetSourceType } from './assetTypes';

const CATEGORIES: ReadonlySet<AssetCategory> = new Set([
  'building',
  'tile',
  'effect',
  'ui',
  'character',
  'fallback',
]);
const SOURCE_TYPES: ReadonlySet<AssetSourceType> = new Set(['image', 'atlas', 'generated']);

export interface ManifestProblem {
  assetId: string | null;
  code: string;
  message: string;
}

export const EMPTY_MANIFEST: AssetManifest = { manifestVersion: '0.0.0', assets: [] };

function validateEntry(e: AssetManifestEntry, problems: ManifestProblem[]): void {
  const id = e.assetId ?? null;
  if (!e.assetId) problems.push({ assetId: id, code: 'MISSING_ID', message: 'assetId is required' });
  if (!CATEGORIES.has(e.category))
    problems.push({ assetId: id, code: 'BAD_CATEGORY', message: `invalid category ${String(e.category)}` });
  if (!SOURCE_TYPES.has(e.sourceType))
    problems.push({ assetId: id, code: 'BAD_SOURCE_TYPE', message: `invalid sourceType ${String(e.sourceType)}` });
  if ((e.sourceType === 'image' || e.sourceType === 'atlas') && !e.source)
    problems.push({ assetId: id, code: 'MISSING_SOURCE', message: `${e.sourceType} requires source` });
  if (e.sourceType === 'atlas' && !e.frame)
    problems.push({ assetId: id, code: 'MISSING_FRAME', message: 'atlas requires frame' });
  if (e.anchor && (!inRange01(e.anchor.x) || !inRange01(e.anchor.y)))
    problems.push({ assetId: id, code: 'BAD_ANCHOR', message: 'anchor x/y must be 0..1' });
  if (e.footprint && (!inFootprint(e.footprint.width) || !inFootprint(e.footprint.height)))
    problems.push({ assetId: id, code: 'BAD_FOOTPRINT', message: 'footprint w/h must be 1..4' });
}

function inRange01(n: number): boolean {
  return typeof n === 'number' && n >= 0 && n <= 1;
}
function inFootprint(n: number): boolean {
  return Number.isInteger(n) && n >= 1 && n <= 4;
}

/** Validate structure, duplicate ids, and fallback references (missing + cycles). */
export function validateManifest(manifest: AssetManifest): ManifestProblem[] {
  const problems: ManifestProblem[] = [];
  if (!manifest.manifestVersion)
    problems.push({ assetId: null, code: 'NO_VERSION', message: 'manifestVersion is required' });

  const ids = new Set<string>();
  for (const e of manifest.assets) {
    validateEntry(e, problems);
    if (e.assetId) {
      if (ids.has(e.assetId))
        problems.push({ assetId: e.assetId, code: 'DUP_ID', message: `duplicate assetId ${e.assetId}` });
      ids.add(e.assetId);
    }
  }

  // Fallback references: must exist, and must not form a cycle.
  const byId = new Map(manifest.assets.filter((a) => a.assetId).map((a) => [a.assetId, a]));
  for (const e of manifest.assets) {
    if (!e.fallbackAssetId) continue;
    if (!byId.has(e.fallbackAssetId)) {
      problems.push({
        assetId: e.assetId ?? null,
        code: 'MISSING_FALLBACK',
        message: `fallbackAssetId ${e.fallbackAssetId} not found`,
      });
      continue;
    }
    // Walk the fallback chain; detect a cycle.
    const seen = new Set<string>([e.assetId]);
    let cur = byId.get(e.fallbackAssetId);
    while (cur?.fallbackAssetId) {
      if (seen.has(cur.assetId)) {
        problems.push({ assetId: e.assetId ?? null, code: 'FALLBACK_CYCLE', message: 'fallback cycle detected' });
        break;
      }
      seen.add(cur.assetId);
      cur = byId.get(cur.fallbackAssetId);
    }
  }
  return problems;
}

export function isManifestValid(manifest: AssetManifest): boolean {
  return validateManifest(manifest).length === 0;
}
