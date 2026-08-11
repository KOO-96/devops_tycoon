/**
 * Test-page entry (NOT the production app). Proves a real WebGL2 context + Pixi init,
 * runs the production image loader scenarios against the real (default routing)
 * AssetManager, and exposes results on window.__productionImageResults (test page only).
 */

import { Application } from 'pixi.js';
import { runProductionImageScenarios, type ScenarioResult } from './scenarios';

interface WebglInfo {
  webgl2: boolean;
  renderer?: string;
}
interface ResultsPayload {
  webgl: WebglInfo;
  pixiInit: boolean;
  scenarios: ScenarioResult[];
  errors: string[];
  allOk: boolean;
}

function webglInfo(): WebglInfo {
  const c = document.createElement('canvas');
  const gl = c.getContext('webgl2');
  if (!gl) return { webgl2: false };
  const dbg = gl.getExtension('WEBGL_debug_renderer_info');
  const renderer = dbg ? String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)) : 'unknown';
  return { webgl2: true, renderer };
}

async function main(): Promise<void> {
  const errors: string[] = [];
  window.addEventListener('error', (e) => errors.push(`error:${e.message}`));
  window.addEventListener('unhandledrejection', (e) =>
    errors.push(`unhandledrejection:${String((e as PromiseRejectionEvent).reason)}`),
  );

  const webgl = webglInfo();
  const app = new Application();
  await app.init({ width: 64, height: 64, preference: 'webgl' });
  const pixiInit = true;
  app.destroy(true, { children: true });

  const scenarios = await runProductionImageScenarios();
  const allOk = scenarios.every((s) => s.ok) && errors.length === 0 && webgl.webgl2;
  const payload: ResultsPayload = { webgl, pixiInit, scenarios, errors, allOk };
  (window as unknown as { __productionImageResults?: ResultsPayload }).__productionImageResults = payload;

  const el = document.createElement('pre');
  el.id = 'results';
  el.setAttribute('data-done', 'true');
  el.textContent = JSON.stringify(payload, null, 2);
  document.body.appendChild(el);
}

void main();
