import { test, expect } from '@playwright/test';

interface Check {
  label: string;
  ok: boolean;
  got: unknown;
}
interface ScenarioResult {
  name: string;
  ok: boolean;
  checks: Check[];
}
interface ResultsPayload {
  webgl: { webgl2: boolean; renderer?: string };
  pixi: { pixiInit: boolean; rendererType?: unknown };
  scenarios: ScenarioResult[];
  errors: string[];
  allOk: boolean;
}

test('asset runtime fallback/checksum/race paths run in real WebGL2', async ({ page }) => {
  const pageErrors: string[] = [];
  page.on('pageerror', (e) => pageErrors.push(`pageerror:${e.message}`));
  page.on('console', (m) => {
    if (m.type() === 'error') pageErrors.push(`console:${m.text()}`);
  });

  await page.goto('/');
  await page.waitForSelector('#results[data-done="true"]', { timeout: 30_000 });
  const results = (await page.evaluate(
    () => (window as unknown as { __assetRuntimeResults: ResultsPayload }).__assetRuntimeResults,
  )) as ResultsPayload;

  // Real WebGL2 + Pixi init.
  expect(results.webgl.webgl2, 'real WebGL2 context').toBe(true);
  expect(results.pixi.pixiInit, 'Pixi Application initialized').toBe(true);
  // eslint-disable-next-line no-console
  console.log('WebGL2 renderer:', results.webgl.renderer);

  // Every scenario passes (report failing checks by name).
  for (const s of results.scenarios) {
    const failing = s.checks.filter((c) => !c.ok);
    expect(s.ok, `${s.name} failing checks: ${JSON.stringify(failing)}`).toBe(true);
  }
  expect(results.scenarios.map((s) => s.name)).toEqual([
    'success',
    'entry_fallback',
    'category_fallback',
    'universal_fallback',
    'checksum_match',
    'checksum_refetch_success',
    'checksum_double_mismatch',
    'transient_then_mismatch',
    'concurrent_acquire',
    'dispose_during_verify',
  ]);

  expect(results.errors, 'no in-page errors').toEqual([]);
  expect(pageErrors, 'no page/console errors').toEqual([]);
  expect(results.allOk).toBe(true);
});
