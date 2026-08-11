/**
 * Production image loading scenarios for the REAL runtime (default routing AssetManager
 * → ProductionImageAssetLoader) in real Chromium/WebGL2. Synthetic PNGs are generated
 * in-page and served via object URLs (real fetch → arrayBuffer → Web Crypto SHA-256 →
 * createImageBitmap → Pixi Texture). No production asset binary is committed.
 */

import { AssetManager } from '../../../src/game/pixi/assets/AssetManager';
import { WebCryptoChecksumVerifier } from '../../../src/game/pixi/assets/assetLoader';
import type { AssetManifest, AssetManifestEntry } from '../../../src/game/pixi/assets/assetTypes';

export interface Check {
  label: string;
  ok: boolean;
  got: unknown;
}
export interface ScenarioResult {
  name: string;
  ok: boolean;
  checks: Check[];
}

async function makePngBytes(color: string): Promise<Uint8Array> {
  const c = document.createElement('canvas');
  c.width = 8;
  c.height = 8;
  const g = c.getContext('2d');
  if (!g) throw new Error('no 2d context');
  g.fillStyle = color;
  g.fillRect(0, 0, 8, 8);
  const blob: Blob = await new Promise((res, rej) =>
    c.toBlob((b) => (b ? res(b) : rej(new Error('toBlob null'))), 'image/png'),
  );
  return new Uint8Array(await blob.arrayBuffer());
}

async function sha256hex(bytes: Uint8Array): Promise<string> {
  return new WebCryptoChecksumVerifier().sha256(bytes);
}

function objectUrl(bytes: Uint8Array): string {
  return URL.createObjectURL(new Blob([bytes as unknown as BlobPart], { type: 'image/png' }));
}

function imageEntry(source: string, checksum: string, version = '1'): AssetManifestEntry {
  return { assetId: 'building.hero.primary', assetVersion: version, category: 'building', sourceType: 'image', source, checksum };
}
function manifest(entry: AssetManifestEntry): AssetManifest {
  return { manifestVersion: entry.assetVersion ?? '1', assets: [entry], categoryFallbacks: {} };
}

function newManager(m: AssetManifest): AssetManager {
  const mgr = new AssetManager({ registerDevelopmentManifest: false });
  mgr.registerManifest(m);
  return mgr;
}

function result(name: string, checks: Check[]): ScenarioResult {
  return { name, ok: checks.every((c) => c.ok), checks };
}

async function scSuccess(): Promise<ScenarioResult> {
  const bytes = await makePngBytes('#48f');
  const url = objectUrl(bytes);
  const mgr = newManager(manifest(imageEntry(url, await sha256hex(bytes))));
  try {
    const h = await mgr.acquire('building.hero.primary');
    const checks: Check[] = [
      { label: 'not fallback', ok: h.fallback === false, got: h.fallback },
      { label: 'has texture', ok: !!h.texture, got: !!h.texture },
      { label: 'tier primary', ok: mgr.lastTierOf('building.hero.primary') === 'primary', got: mgr.lastTierOf('building.hero.primary') },
    ];
    h.release();
    return result('image_success', checks);
  } finally {
    URL.revokeObjectURL(url);
    await mgr.disposeAll();
  }
}

async function scChecksumMismatchFallback(): Promise<ScenarioResult> {
  const bytes = await makePngBytes('#f84');
  const url = objectUrl(bytes);
  const mgr = newManager(manifest(imageEntry(url, '0'.repeat(64)))); // wrong checksum
  try {
    const h = await mgr.acquire('building.hero.primary');
    const checks: Check[] = [
      { label: 'falls back on corrupt', ok: h.fallback === true, got: h.fallback },
      { label: 'has (fallback) texture', ok: !!h.texture, got: !!h.texture },
    ];
    h.release();
    return result('checksum_mismatch_fallback', checks);
  } finally {
    URL.revokeObjectURL(url);
    await mgr.disposeAll();
  }
}

async function scHttp404(): Promise<ScenarioResult> {
  const mgr = newManager(manifest(imageEntry('/__no_such_asset__.png', '0'.repeat(64))));
  try {
    const h = await mgr.acquire('building.hero.primary');
    const checks: Check[] = [{ label: '404 → fallback', ok: h.fallback === true, got: h.fallback }];
    h.release();
    return result('http_404_terminal', checks);
  } finally {
    await mgr.disposeAll();
  }
}

async function scConcurrent(): Promise<ScenarioResult> {
  const bytes = await makePngBytes('#8f4');
  const url = objectUrl(bytes);
  const mgr = newManager(manifest(imageEntry(url, await sha256hex(bytes))));
  try {
    const [h1, h2] = await Promise.all([mgr.acquire('building.hero.primary'), mgr.acquire('building.hero.primary')]);
    const checks: Check[] = [
      { label: 'shared texture', ok: h1.texture === h2.texture, got: h1.texture === h2.texture },
      { label: 'not fallback', ok: h1.fallback === false, got: h1.fallback },
    ];
    h1.release();
    h2.release();
    return result('concurrent_acquire', checks);
  } finally {
    URL.revokeObjectURL(url);
    await mgr.disposeAll();
  }
}

async function scDisposeDuringFetch(): Promise<ScenarioResult> {
  const bytes = await makePngBytes('#84f');
  const url = objectUrl(bytes);
  const mgr = newManager(manifest(imageEntry(url, await sha256hex(bytes))));
  let threw = false;
  let handleFallback: boolean | undefined;
  try {
    const acquiring = mgr.acquire('building.hero.primary');
    const disposing = mgr.disposeAll();
    const h = await acquiring;
    handleFallback = h.fallback;
    await disposing;
  } catch {
    threw = true;
  } finally {
    URL.revokeObjectURL(url);
  }
  return result('dispose_during_fetch', [
    { label: 'no throw on dispose race', ok: threw === false, got: threw },
    { label: 'safe handle', ok: handleFallback === true || handleFallback === false, got: handleFallback },
  ]);
}

async function scVersionIsolation(): Promise<ScenarioResult> {
  const bytes = await makePngBytes('#4f8');
  const url = objectUrl(bytes);
  const checksum = await sha256hex(bytes);
  const mgr = newManager(manifest(imageEntry(url, checksum, '1')));
  try {
    const h1 = await mgr.acquire('building.hero.primary');
    mgr.replaceManifest(manifest(imageEntry(url, checksum, '2')));
    const h2 = await mgr.acquire('building.hero.primary');
    const checks: Check[] = [
      { label: 'v1 handle', ok: h1.assetVersion === '1', got: h1.assetVersion },
      { label: 'v2 handle', ok: h2.assetVersion === '2', got: h2.assetVersion },
    ];
    h1.release();
    h2.release();
    return result('version_isolation', checks);
  } finally {
    URL.revokeObjectURL(url);
    await mgr.disposeAll();
  }
}

async function scAtlasUnsupported(): Promise<ScenarioResult> {
  const entry: AssetManifestEntry = { assetId: 'ui.badge.primary', assetVersion: '1', category: 'ui', sourceType: 'atlas', source: '/a.json', frame: 'f' };
  const mgr = newManager({ manifestVersion: '1', assets: [entry], categoryFallbacks: {} });
  try {
    const h = await mgr.acquire('ui.badge.primary');
    const checks: Check[] = [{ label: 'atlas → fallback (unsupported, not generated)', ok: h.fallback === true, got: h.fallback }];
    h.release();
    return result('atlas_unsupported', checks);
  } finally {
    await mgr.disposeAll();
  }
}

export async function runProductionImageScenarios(): Promise<ScenarioResult[]> {
  return [
    await scSuccess(),
    await scChecksumMismatchFallback(),
    await scHttp404(),
    await scConcurrent(),
    await scDisposeDuringFetch(),
    await scVersionIsolation(),
    await scAtlasUnsupported(),
  ];
}
