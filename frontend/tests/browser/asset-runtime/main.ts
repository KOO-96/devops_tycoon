/**
 * Test-page entry (NOT the production app). Proves a real WebGL2 context + Pixi
 * init, runs the asset-runtime scenarios against the real AssetManager, and exposes
 * the results on the TEST page only (window.__assetRuntimeResults on this page).
 */

import { Application } from 'pixi.js';
import { runAllScenarios, type ScenarioResult } from './assetRuntimeScenarios';

interface WebglInfo {
  webgl2: boolean;
  renderer?: string;
}
interface PixiInfo {
  pixiInit: boolean;
  rendererType?: unknown;
}

function webglInfo(): WebglInfo {
  const c = document.createElement('canvas');
  const gl = c.getContext('webgl2');
  if (!gl) return { webgl2: false };
  const dbg = gl.getExtension('WEBGL_debug_renderer_info');
  const renderer = dbg ? String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)) : 'unknown';
  return { webgl2: true, renderer };
}

async function pixiInfo(): Promise<PixiInfo> {
  const app = new Application();
  await app.init({ width: 64, height: 64, preference: 'webgl' });
  const rendererType = (app.renderer as unknown as { type?: unknown }).type;
  app.destroy(true, { children: true });
  return { pixiInit: true, rendererType };
}

interface ResultsPayload {
  webgl: WebglInfo;
  pixi: PixiInfo;
  scenarios: ScenarioResult[];
  errors: string[];
  allOk: boolean;
}

async function main(): Promise<void> {
  const errors: string[] = [];
  window.addEventListener('error', (e) => errors.push(`error:${e.message}`));
  window.addEventListener('unhandledrejection', (e) =>
    errors.push(`unhandledrejection:${String((e as PromiseRejectionEvent).reason)}`),
  );

  const webgl = webglInfo();
  const pixi = await pixiInfo();
  const scenarios = await runAllScenarios();
  const allOk = scenarios.every((s) => s.ok) && errors.length === 0 && webgl.webgl2;

  const payload: ResultsPayload = { webgl, pixi, scenarios, errors, allOk };
  (window as unknown as { __assetRuntimeResults?: ResultsPayload }).__assetRuntimeResults = payload;

  const el = document.createElement('pre');
  el.id = 'results';
  el.setAttribute('data-done', 'true');
  el.textContent = JSON.stringify(payload, null, 2);
  document.body.appendChild(el);
}

void main();
