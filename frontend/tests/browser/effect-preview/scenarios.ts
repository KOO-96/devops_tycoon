/**
 * Isolated effect-preview scenarios (candidate #005, category `effect`). Uses the REAL
 * AssetManager + default RoutingAssetLoader/ProductionImageAssetLoader against the REAL
 * served production effect PNG (`/assets/effect/network-flow.png`, real checksum). No
 * mock texture, NO simulation/event wiring — this only validates the image resource's
 * runtime behavior: PRIMARY load, alpha blending, shared texture across many instances,
 * lifecycle recreate, and shared-texture destroy safety, on a real WebGL2 frame.
 */
import { Application, Sprite, Graphics } from 'pixi.js';
import { AssetManager } from '../../../src/game/pixi/assets/AssetManager';
import type { AssetManifest, AssetManifestEntry } from '../../../src/game/pixi/assets/assetTypes';

export interface Check { label: string; ok: boolean; got: unknown }
export interface ScenarioResult { name: string; ok: boolean; checks: Check[] }

const EFFECT_ID = 'effect.network-flow.primary';
const EFFECT_SOURCE = '/assets/effect/network-flow.png';
const EFFECT_CHECKSUM = 'd4c2dd4e7873479cc6ceff00394c28c7149561d468bb0f56d65b257b122b56e9';

function entry(): AssetManifestEntry {
  return { assetId: EFFECT_ID, assetVersion: '1', category: 'effect', sourceType: 'image', source: EFFECT_SOURCE, checksum: EFFECT_CHECKSUM };
}
function manifest(): AssetManifest {
  return { manifestVersion: '1', assets: [entry()], categoryFallbacks: {} };
}
function newManager(): AssetManager {
  const m = new AssetManager({ registerDevelopmentManifest: false });
  m.registerManifest(manifest());
  return m;
}
function result(name: string, checks: Check[]): ScenarioResult {
  return { name, ok: checks.every((c) => c.ok), checks };
}
async function makeApp(w: number, h: number): Promise<Application> {
  const app = new Application();
  await app.init({ width: w, height: h, preference: 'webgl', backgroundAlpha: 0 });
  return app;
}
function countPixels(px: Uint8ClampedArray | Uint8Array): { opaque: number; anyAlpha: number; cyan: number } {
  let opaque = 0, anyAlpha = 0, cyan = 0;
  for (let i = 0; i < px.length; i += 4) {
    const r = px[i] ?? 0, g = px[i + 1] ?? 0, b = px[i + 2] ?? 0, a = px[i + 3] ?? 0;
    if (a > 0) anyAlpha++;
    if (a > 200) opaque++;
    if (a > 60 && g > 150 && b > 130 && r < 200) cyan++; // the flow beam's cyan
  }
  return { opaque, anyAlpha, cyan };
}

/** 1. Real loader → PRIMARY (not fallback). */
async function scPrimary(): Promise<ScenarioResult> {
  const m = newManager();
  try {
    const h = await m.acquire(EFFECT_ID);
    const checks: Check[] = [
      { label: 'not fallback', ok: h.fallback === false, got: h.fallback },
      { label: 'has texture', ok: !!h.texture, got: !!h.texture },
      { label: 'tier primary', ok: m.lastTierOf(EFFECT_ID) === 'primary', got: m.lastTierOf(EFFECT_ID) },
      { label: 'category effect id', ok: h.assetId === EFFECT_ID, got: h.assetId },
    ];
    h.release();
    return result('effect_primary_load', checks);
  } finally {
    await m.disposeAll();
  }
}

/** 2. Single-instance render → non-empty pixels (real WebGL2 frame). */
async function scSingleRender(): Promise<ScenarioResult> {
  const m = newManager();
  const app = await makeApp(256, 96);
  try {
    const h = await m.acquire(EFFECT_ID);
    const s = new Sprite(h.texture ?? undefined);
    s.width = 240; s.height = 80; s.position.set(8, 8);
    app.stage.addChild(s);
    app.render();
    const out = app.renderer.extract.pixels(app.stage);
    const c = countPixels(out.pixels);
    h.release();
    return result('single_instance_render', [
      { label: 'non-empty (alpha>0 pixels)', ok: c.anyAlpha > 0, got: c.anyAlpha },
      { label: 'flow beam cyan visible', ok: c.cyan > 0, got: c.cyan },
    ]);
  } finally {
    app.destroy(true, { children: true });
    await m.disposeAll();
  }
}

/** 3. Alpha blending over an opaque background. */
async function scAlphaBlend(): Promise<ScenarioResult> {
  const m = newManager();
  const app = await makeApp(256, 96);
  try {
    const bg = new Graphics();
    bg.rect(0, 0, 256, 96).fill({ color: 0xcc2222 }); // opaque red background
    app.stage.addChild(bg);
    const h = await m.acquire(EFFECT_ID);
    const s = new Sprite(h.texture ?? undefined);
    s.width = 240; s.height = 80; s.position.set(8, 8);
    app.stage.addChild(s);
    app.render();
    const out = app.renderer.extract.pixels(app.stage);
    const px = out.pixels; const W = out.width;
    const at = (x: number, y: number): [number, number, number, number] => {
      const i = (y * W + x) * 4; return [px[i] ?? 0, px[i + 1] ?? 0, px[i + 2] ?? 0, px[i + 3] ?? 0];
    };
    // top-left corner: effect fully transparent there → background red preserved
    const corner = at(3, 3);
    // beam center band (mid height): blended → not pure red (green/blue raised)
    let blended = 0;
    for (let x = 20; x < 230; x++) { const [, g, b] = at(x, 48); if (g > 80 && b > 80) blended++; }
    h.release();
    return result('alpha_blend', [
      { label: 'transparent area keeps red bg', ok: corner[0] > 150 && corner[1] < 90 && corner[2] < 90 && corner[3] > 200, got: corner },
      { label: 'beam area blended over bg', ok: blended > 10, got: blended },
    ]);
  } finally {
    app.destroy(true, { children: true });
    await m.disposeAll();
  }
}

/** 4. Many instances share ONE texture (single load), render without corruption. */
async function scMultiInstance(): Promise<ScenarioResult> {
  const m = newManager();
  const app = await makeApp(256, 256);
  const checks: Check[] = [];
  try {
    const handles = await Promise.all([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16].map(() => m.acquire(EFFECT_ID)));
    const tex0 = handles[0]!.texture;
    checks.push({ label: 'all 16 share one texture', ok: handles.every((h) => h.texture === tex0), got: handles.every((h) => h.texture === tex0) });
    checks.push({ label: 'refCount == 16', ok: m.refCountOf(EFFECT_ID) === 16, got: m.refCountOf(EFFECT_ID) });
    handles.forEach((h, i) => { const s = new Sprite(h.texture ?? undefined); s.width = 240; s.height = 14; s.position.set(8, 4 + i * 15); app.stage.addChild(s); });
    app.render();
    const c = countPixels(app.renderer.extract.pixels(app.stage).pixels);
    const gl = (app.renderer as unknown as { gl?: WebGL2RenderingContext }).gl;
    checks.push({ label: '16 instances render non-empty', ok: c.anyAlpha > 0, got: c.anyAlpha });
    checks.push({ label: 'no context loss', ok: !gl || !gl.isContextLost(), got: gl ? gl.isContextLost() : 'no-gl' });
    handles.forEach((h) => h.release());
    return result('multi_instance_shared_texture', checks);
  } finally {
    app.destroy(true, { children: true });
    await m.disposeAll();
  }
}

/** 5. Destroying one sprite must NOT destroy the shared texture; others still render. */
async function scSharedDestroySafety(): Promise<ScenarioResult> {
  const m = newManager();
  const app = await makeApp(256, 128);
  try {
    const h = await m.acquire(EFFECT_ID);
    const sprites = [0, 1, 2, 3].map((i) => { const s = new Sprite(h.texture ?? undefined); s.width = 240; s.height = 24; s.position.set(8, 4 + i * 30); app.stage.addChild(s); return s; });
    app.render();
    sprites[0]!.destroy(); // destroy ONE sprite (default: does not destroy the texture)
    app.render();
    const c = countPixels(app.renderer.extract.pixels(app.stage).pixels);
    const texAlive = h.texture && !(h.texture as unknown as { destroyed?: boolean }).destroyed;
    h.release();
    return result('shared_texture_destroy_safety', [
      { label: 'shared texture still alive after one sprite destroy', ok: !!texAlive, got: !!texAlive },
      { label: 'remaining sprites still render', ok: c.anyAlpha > 0, got: c.anyAlpha },
    ]);
  } finally {
    app.destroy(true, { children: true });
    await m.disposeAll();
  }
}

/** 6. Lifecycle: acquire → render → release+collect → re-acquire → render again. */
async function scLifecycle(): Promise<ScenarioResult> {
  const m = newManager();
  const app = await makeApp(256, 96);
  try {
    const h1 = await m.acquire(EFFECT_ID);
    const s1 = new Sprite(h1.texture ?? undefined); s1.width = 240; s1.height = 80; s1.position.set(8, 8); app.stage.addChild(s1);
    app.render();
    const c1 = countPixels(app.renderer.extract.pixels(app.stage).pixels);
    h1.release(); s1.destroy(); m.disposeStale();
    // re-acquire fresh
    const h2 = await m.acquire(EFFECT_ID);
    const s2 = new Sprite(h2.texture ?? undefined); s2.width = 240; s2.height = 80; s2.position.set(8, 8); app.stage.addChild(s2);
    app.render();
    const c2 = countPixels(app.renderer.extract.pixels(app.stage).pixels);
    h2.release();
    return result('lifecycle_recreate', [
      { label: 'first render non-empty', ok: c1.anyAlpha > 0, got: c1.anyAlpha },
      { label: 're-acquire not fallback', ok: h2.fallback === false, got: h2.fallback },
      { label: 'second render non-empty', ok: c2.anyAlpha > 0, got: c2.anyAlpha },
    ]);
  } finally {
    app.destroy(true, { children: true });
    await m.disposeAll();
  }
}

/** 7. AssetManager handle/refcount contract: shared cache, individual + final release. */
async function scRefcount(): Promise<ScenarioResult> {
  const m = newManager();
  try {
    const a = await m.acquire(EFFECT_ID);
    const b = await m.acquire(EFFECT_ID);
    const c = await m.acquire(EFFECT_ID);
    const checks: Check[] = [
      { label: 'shared texture', ok: a.texture === b.texture && b.texture === c.texture, got: a.texture === b.texture },
      { label: 'refCount 3', ok: m.refCountOf(EFFECT_ID) === 3, got: m.refCountOf(EFFECT_ID) },
    ];
    a.release(); b.release();
    checks.push({ label: 'refCount 1 after 2 releases', ok: m.refCountOf(EFFECT_ID) === 1, got: m.refCountOf(EFFECT_ID) });
    c.release();
    checks.push({ label: 'refCount 0 after final release', ok: m.refCountOf(EFFECT_ID) === 0, got: m.refCountOf(EFFECT_ID) });
    return result('handle_refcount', checks);
  } finally {
    await m.disposeAll();
  }
}

export async function runEffectPreviewScenarios(): Promise<ScenarioResult[]> {
  return [
    await scPrimary(),
    await scSingleRender(),
    await scAlphaBlend(),
    await scMultiInstance(),
    await scSharedDestroySafety(),
    await scLifecycle(),
    await scRefcount(),
  ];
}
