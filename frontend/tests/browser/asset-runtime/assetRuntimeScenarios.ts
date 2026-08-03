/**
 * Real-browser scenarios for the asset runtime fallback / checksum / race paths.
 * Uses the REAL AssetManager + manifest validator + retry state machine + versioned
 * cache + Asset Handle + real Pixi Textures; only the Loader's responses are scripted
 * (injected via the public constructor DI — no production hook).
 */

import { AssetManager } from '../../../src/game/pixi/assets/AssetManager';
import { UNIVERSAL_FALLBACK_ASSET_ID } from '../../../src/game/pixi/assets/generatedBuildingAsset';
import type { AssetManifest, AssetManifestEntry } from '../../../src/game/pixi/assets/assetTypes';
import { ControlledAssetLoader, type LoaderPlan, type Outcome } from './controlledAssetLoader';
import { snapshot, type AssetRuntimeDebugSnapshot } from './instrumentation';

export interface ScenarioResult {
  name: string;
  ok: boolean;
  checks: Array<{ label: string; ok: boolean; got: unknown }>;
  snapshot: AssetRuntimeDebugSnapshot;
}

const GOOD = 'a'.repeat(64);
const BAD = 'b'.repeat(64);

// Per-attempt timeout (>=1000ms) never fires; backoff (<1000ms) is instant.
const fastSleep = (ms: number): Promise<void> =>
  ms >= 1000 ? new Promise<void>(() => {}) : Promise.resolve();

const entry = (assetId: string, extra: Partial<AssetManifestEntry> = {}): AssetManifestEntry => ({
  assetId,
  category: assetId.startsWith('fallback') ? 'fallback' : 'building',
  sourceType: 'generated',
  assetVersion: 'v',
  ...extra,
});

function tierManifest(): AssetManifest {
  return {
    manifestVersion: 'v',
    assets: [
      entry('primary', { fallbackAssetId: 'entryFb' }),
      entry('primary2'),
      entry('entryFb'),
      entry('catFb'),
      entry(UNIVERSAL_FALLBACK_ASSET_ID),
    ],
    categoryFallbacks: { building: 'catFb' },
  };
}
function checksumManifest(checksum: string): AssetManifest {
  return {
    manifestVersion: 'v',
    assets: [entry('img', { checksum }), entry('catFb'), entry(UNIVERSAL_FALLBACK_ASSET_ID)],
    categoryFallbacks: { building: 'catFb' },
  };
}

function makeManager(plan: LoaderPlan, manifest: AssetManifest): { m: AssetManager; loader: ControlledAssetLoader } {
  const loader = new ControlledAssetLoader(plan);
  const m = new AssetManager({ loader, sleep: fastSleep, registerDevelopmentManifest: false });
  m.registerManifest(manifest);
  return { m, loader };
}

const ok = (checksum?: string): Outcome => (checksum !== undefined ? { kind: 'ok', checksum } : { kind: 'ok' });
const err = (k: 'network' | 'server' | 'not_found' | 'client' | 'decode'): Outcome => ({ kind: 'error', errorKind: k });

function result(
  name: string,
  m: AssetManager,
  loader: ControlledAssetLoader,
  ids: string[],
  checks: Array<{ label: string; ok: boolean; got: unknown }>,
): ScenarioResult {
  return { name, ok: checks.every((c) => c.ok), checks, snapshot: snapshot(m, loader, ids) };
}

const wait = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms));

export async function runAllScenarios(): Promise<ScenarioResult[]> {
  const out: ScenarioResult[] = [];

  // 1. success
  {
    const { m, loader } = makeManager(() => ok(), tierManifest());
    const h = await m.acquire('primary2');
    out.push(
      result('success', m, loader, ['primary2'], [
        { label: 'not fallback', ok: h.fallback === false, got: h.fallback },
        { label: 'texture present', ok: h.texture !== null, got: h.texture !== null },
        { label: 'tier primary', ok: m.lastTierOf('primary2') === 'primary', got: m.lastTierOf('primary2') },
        { label: 'refCount 1', ok: m.refCountOf('primary2') === 1, got: m.refCountOf('primary2') },
        { label: 'one load', ok: loader.calls.length === 1, got: loader.calls.length },
      ]),
    );
    h.release();
    await m.disposeAll();
  }

  // 2. entry fallback
  {
    const { m, loader } = makeManager(({ assetId }) => (assetId === 'primary' ? err('client') : ok()), tierManifest());
    const h = await m.acquire('primary');
    out.push(
      result('entry_fallback', m, loader, ['primary', 'entryFb', 'catFb'], [
        { label: 'tier entry', ok: m.lastTierOf('primary') === 'entry', got: m.lastTierOf('primary') },
        { label: 'fallback true', ok: h.fallback === true, got: h.fallback },
        { label: 'catFb not loaded', ok: !loader.calls.some((c) => c.assetId === 'catFb'), got: loader.calls.map((c) => c.assetId) },
      ]),
    );
    h.release();
    await m.disposeAll();
  }

  // 3. category fallback
  {
    const { m, loader } = makeManager(({ assetId }) => (assetId === 'primary2' ? err('client') : ok()), tierManifest());
    const h = await m.acquire('primary2');
    out.push(
      result('category_fallback', m, loader, ['primary2', 'catFb'], [
        { label: 'tier category', ok: m.lastTierOf('primary2') === 'category', got: m.lastTierOf('primary2') },
        { label: 'universal not loaded', ok: !loader.calls.some((c) => c.assetId === UNIVERSAL_FALLBACK_ASSET_ID), got: loader.calls.map((c) => c.assetId) },
        { label: 'catFb refCount 1', ok: m.refCountOf('catFb') === 1, got: m.refCountOf('catFb') },
      ]),
    );
    h.release();
    await m.disposeAll();
  }

  // 4. universal fallback
  {
    const fail = new Set(['primary', 'entryFb', 'catFb']);
    const { m, loader } = makeManager(({ assetId }) => (fail.has(assetId) ? err('client') : ok()), tierManifest());
    const h = await m.acquire('primary');
    out.push(
      result('universal_fallback', m, loader, ['primary'], [
        { label: 'tier universal', ok: m.lastTierOf('primary') === 'universal', got: m.lastTierOf('primary') },
        { label: 'fallback true', ok: h.fallback === true, got: h.fallback },
        { label: 'texture present', ok: h.texture !== null, got: h.texture !== null },
      ]),
    );
    h.release();
    await m.disposeAll();
  }

  // 5. checksum match
  {
    const { m, loader } = makeManager(() => ok(GOOD), checksumManifest(GOOD));
    const h = await m.acquire('img');
    out.push(
      result('checksum_match', m, loader, ['img'], [
        { label: 'not fallback', ok: h.fallback === false, got: h.fallback },
        { label: 'one load, no refetch', ok: loader.calls.length === 1, got: loader.calls.length },
      ]),
    );
    h.release();
    await m.disposeAll();
  }

  // 6. checksum refetch success
  {
    const { m, loader } = makeManager(({ mode }) => ok(mode === 'normal' ? BAD : GOOD), checksumManifest(GOOD));
    const h = await m.acquire('img');
    const modes = loader.calls.map((c) => c.mode);
    out.push(
      result('checksum_refetch_success', m, loader, ['img'], [
        { label: 'not fallback', ok: h.fallback === false, got: h.fallback },
        { label: 'modes normal,integrity', ok: JSON.stringify(modes) === JSON.stringify(['normal', 'integrity_refetch']), got: modes },
        { label: 'refetch bypassCache', ok: loader.calls[1]?.bypassCache === true, got: loader.calls[1]?.bypassCache },
        { label: 'corrupt destroyed', ok: loader.textureDestroys >= 1, got: loader.textureDestroys },
      ]),
    );
    h.release();
    await m.disposeAll();
  }

  // 7. double mismatch → fallback
  {
    const { m, loader } = makeManager(({ assetId }) => (assetId === 'img' ? ok(BAD) : ok()), checksumManifest(GOOD));
    const h = await m.acquire('img');
    const imgCalls = loader.calls.filter((c) => c.assetId === 'img').length;
    out.push(
      result('checksum_double_mismatch', m, loader, ['img'], [
        { label: 'fallback true', ok: h.fallback === true, got: h.fallback },
        { label: 'img attempts = 2', ok: imgCalls === 2, got: imgCalls },
        { label: 'both corrupt destroyed', ok: loader.textureDestroys >= 2, got: loader.textureDestroys },
      ]),
    );
    h.release();
    await m.disposeAll();
  }

  // 8. transient then mismatch (<=4 attempts total)
  {
    let imgN = 0;
    const plan: LoaderPlan = ({ assetId, mode }) => {
      if (assetId !== 'img') return ok();
      imgN += 1;
      if (mode === 'normal' && imgN === 1) return err('server'); // transient
      if (mode === 'normal') return ok(BAD);
      return ok(GOOD); // integrity refetch
    };
    const { m, loader } = makeManager(plan, checksumManifest(GOOD));
    const h = await m.acquire('img');
    const imgModes = loader.calls.filter((c) => c.assetId === 'img').map((c) => c.mode);
    out.push(
      result('transient_then_mismatch', m, loader, ['img'], [
        { label: 'not fallback', ok: h.fallback === false, got: h.fallback },
        { label: 'modes normal,normal,integrity', ok: JSON.stringify(imgModes) === JSON.stringify(['normal', 'normal', 'integrity_refetch']), got: imgModes },
        { label: 'attempts <= 4', ok: imgModes.length <= 4, got: imgModes.length },
      ]),
    );
    h.release();
    await m.disposeAll();
  }

  // 9. concurrent acquire shares one refetch
  {
    const { m, loader } = makeManager(({ mode }) => ok(mode === 'normal' ? BAD : GOOD), checksumManifest(GOOD));
    const [h1, h2] = await Promise.all([m.acquire('img'), m.acquire('img')]);
    const refetches = loader.calls.filter((c) => c.assetId === 'img' && c.mode === 'integrity_refetch').length;
    out.push(
      result('concurrent_acquire', m, loader, ['img'], [
        { label: 'same texture', ok: h1.texture === h2.texture, got: h1.texture === h2.texture },
        { label: 'one integrity refetch', ok: refetches === 1, got: refetches },
        { label: 'refCount 2', ok: m.refCountOf('img') === 2, got: m.refCountOf('img') },
      ]),
    );
    h1.release();
    h2.release();
    await m.disposeAll();
  }

  // 10. dispose during (integrity) verify
  {
    // normal → BAD immediately (texture created); integrity_refetch → delayed GOOD.
    const plan: LoaderPlan = ({ mode }) => (mode === 'normal' ? ok(BAD) : { kind: 'delay', ms: 60, then: ok(GOOD) });
    const { m, loader } = makeManager(plan, checksumManifest(GOOD));
    const acquiring = m.acquire('img');
    await wait(10); // let normal load + mismatch happen, integrity refetch now in-flight
    await m.disposeAll(); // dispose mid-refetch
    const h = await acquiring;
    out.push(
      result('dispose_during_verify', m, loader, ['img'], [
        { label: 'no result registered (cache 0)', ok: m.cacheSize() === 0, got: m.cacheSize() },
        { label: 'corrupt destroyed', ok: loader.textureDestroys >= 1, got: loader.textureDestroys },
        { label: 'handle detached/fallback', ok: h.fallback === true, got: h.fallback },
      ]),
    );
  }

  return out;
}
