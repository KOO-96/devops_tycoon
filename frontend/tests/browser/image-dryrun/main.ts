/**
 * P4 end-to-end proof: the browser fetches the GENERATOR-PRODUCED manifest.json over
 * real HTTP, feeds it to the REAL AssetManager (default RoutingAssetLoader →
 * ProductionImageAssetLoader), which fetches the synthetic PNG over real HTTP, verifies
 * the Web Crypto checksum, decodes it, builds a real Pixi Texture, and RENDERS it as a
 * Sprite in a real WebGL2 scene. Proves generator output ↔ real app consumption.
 */

import { Application, Sprite } from 'pixi.js';
import { AssetManager } from '../../../src/game/pixi/assets/AssetManager';
import type { AssetManifest } from '../../../src/game/pixi/assets/assetTypes';

interface ResultsPayload {
  webgl2: boolean;
  manifestFromGenerator: boolean;
  manifestVersion: string;
  targetAssetId: string;
  fallback: boolean;
  hasTexture: boolean;
  rendered: boolean;
  manifestProblems: number;
  errors: string[];
  allOk: boolean;
}

async function main(): Promise<void> {
  const errors: string[] = [];
  window.addEventListener('error', (e) => errors.push(`error:${e.message}`));
  window.addEventListener('unhandledrejection', (e) =>
    errors.push(`unhandledrejection:${String((e as PromiseRejectionEvent).reason)}`),
  );

  const gl = document.createElement('canvas').getContext('webgl2');
  const webgl2 = !!gl;

  const app = new Application();
  await app.init({ width: 128, height: 128, preference: 'webgl' });
  document.body.appendChild(app.canvas);

  // 1. Fetch the GENERATOR-PRODUCED manifest over real HTTP.
  const manifest = (await (await fetch('/manifest.json')).json()) as AssetManifest;
  const manifestFromGenerator =
    typeof manifest.manifestVersion === 'string' && Array.isArray(manifest.assets) && manifest.assets.length > 0;

  // 2. Feed it to the REAL runtime (default routing → ProductionImageAssetLoader).
  const mgr = new AssetManager({ registerDevelopmentManifest: false });
  const problems = mgr.registerManifest(manifest);
  const target = manifest.assets.find((a) => a.assetId.startsWith('building')) ?? manifest.assets[0];
  if (!target) throw new Error('manifest has no assets');

  // 3. Acquire → real fetch of the PNG + Web Crypto checksum + decode + Texture.
  const handle = await mgr.acquire(target.assetId);

  // 4. Render it as a Sprite in the real WebGL2 scene.
  let rendered = false;
  if (handle.texture) {
    const sprite = new Sprite(handle.texture);
    app.stage.addChild(sprite);
    app.renderer.render(app.stage);
    rendered = true;
  }

  const payload: ResultsPayload = {
    webgl2,
    manifestFromGenerator,
    manifestVersion: manifest.manifestVersion,
    targetAssetId: target.assetId,
    fallback: handle.fallback,
    hasTexture: !!handle.texture,
    rendered,
    manifestProblems: problems.length,
    errors,
    allOk:
      webgl2 &&
      manifestFromGenerator &&
      !handle.fallback &&
      !!handle.texture &&
      rendered &&
      problems.length === 0 &&
      errors.length === 0,
  };
  handle.release();

  (window as unknown as { __imageDryrunResults?: ResultsPayload }).__imageDryrunResults = payload;
  const el = document.createElement('pre');
  el.id = 'results';
  el.setAttribute('data-done', 'true');
  el.textContent = JSON.stringify(payload, null, 2);
  document.body.appendChild(el);
}

void main();
