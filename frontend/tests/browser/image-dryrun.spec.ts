import { test, expect } from '@playwright/test';

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

test('P4: generator manifest + synthetic image consumed by the real app in WebGL2', async ({ page }) => {
  const pageErrors: string[] = [];
  page.on('pageerror', (e) => pageErrors.push(`pageerror:${e.message}`));
  page.on('console', (m) => {
    if (m.type() === 'error') pageErrors.push(`console:${m.text()}`);
  });

  await page.goto('/');
  await page.waitForSelector('#results[data-done="true"]', { timeout: 30_000 });
  const r = (await page.evaluate(
    () => (window as unknown as { __imageDryrunResults: ResultsPayload }).__imageDryrunResults,
  )) as ResultsPayload;

  expect(r.webgl2, 'real WebGL2').toBe(true);
  expect(r.manifestFromGenerator, 'manifest came from the generator').toBe(true);
  expect(r.manifestProblems, 'manifest is runtime-valid').toBe(0);
  expect(r.hasTexture, 'real texture built from fetched bytes').toBe(true);
  expect(r.fallback, 'loaded as PRIMARY (checksum matched, not fallback)').toBe(false);
  expect(r.rendered, 'rendered a Sprite in the scene').toBe(true);
  expect(r.errors, 'no in-page errors').toEqual([]);
  expect(pageErrors, 'no page/console errors').toEqual([]);
  expect(r.allOk).toBe(true);
});
