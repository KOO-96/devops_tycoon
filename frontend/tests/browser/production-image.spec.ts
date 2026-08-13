import { test, expect } from '@playwright/test';

interface Check { label: string; ok: boolean; got: unknown }
interface ScenarioResult { name: string; ok: boolean; checks: Check[] }
interface ResultsPayload {
  webgl: { webgl2: boolean; renderer?: string };
  pixiInit: boolean;
  scenarios: ScenarioResult[];
  errors: string[];
  allOk: boolean;
}

test('production image loader: fetch/checksum/decode/fallback in real WebGL2', async ({ page }) => {
  const pageErrors: string[] = [];
  const detachedWarnings: string[] = [];
  page.on('pageerror', (e) => pageErrors.push(`pageerror:${e.message}`));
  page.on('console', (m) => {
    if (m.type() === 'error') pageErrors.push(`console:${m.text()}`);
    // The ImageBitmap-lifetime bug surfaced ONLY as a WebGL warning, never an error.
    if (/detached/i.test(m.text())) detachedWarnings.push(m.text());
  });

  await page.goto('/');
  await page.waitForSelector('#results[data-done="true"]', { timeout: 30_000 });
  const results = (await page.evaluate(
    () => (window as unknown as { __productionImageResults: ResultsPayload }).__productionImageResults,
  )) as ResultsPayload;

  expect(results.webgl.webgl2, 'real WebGL2 context').toBe(true);
  expect(results.pixiInit, 'Pixi Application initialized').toBe(true);
  // eslint-disable-next-line no-console
  console.log('WebGL2 renderer:', results.webgl.renderer);

  for (const s of results.scenarios) {
    const failing = s.checks.filter((c) => !c.ok);
    expect(s.ok, `${s.name} failing: ${JSON.stringify(failing)}`).toBe(true);
  }
  expect(results.scenarios.map((s) => s.name)).toEqual([
    'image_success',
    'real_frame_render',
    'checksum_mismatch_fallback',
    'http_404_terminal',
    'concurrent_acquire',
    'dispose_during_fetch',
    'version_isolation',
    'atlas_unsupported',
  ]);
  expect(results.errors, 'no in-page errors').toEqual([]);
  expect(pageErrors, 'no page/console errors').toEqual([]);
  expect(detachedWarnings, 'no "source data has been detached" WebGL warning').toEqual([]);
  expect(results.allOk).toBe(true);
});
