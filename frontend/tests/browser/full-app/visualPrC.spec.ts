/**
 * Full-app browser smoke for Visual PR C. Requires the app stack running (FastAPI on
 * :8000 + Vite dev proxying to it) — see docs/operations/visual-pr-c-live-verification.md.
 * Verifies real-browser runtime lifecycle: single canvas / single game socket, 50+
 * nodes, route round-trips, teardown, and no console/page/WebGL errors — with the
 * REAL app (production AppProviders + injected app-scoped AssetManager + generated
 * loader). Instrumentation is Playwright-side only (no product hook).
 */

import { test, expect, type Page } from '@playwright/test';
import { INIT_SCRIPT } from './instrumentation';

const API = process.env.VISUAL_C_BASE_URL ?? 'http://localhost:5173';

async function createSession(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/api/v1/game-sessions`, { data: { seed: 7, users: 5 } });
  expect(res.ok(), 'create session').toBeTruthy();
  const body = (await res.json()) as { session_id: string };
  return body.session_id;
}

async function addNodes(page: Page, sid: string, kind: string, prefix: string, n: number): Promise<void> {
  for (let i = 0; i < n; i++) {
    await page.request.post(`${API}/api/v1/game-sessions/${sid}/commands`, {
      data: { command_id: `${prefix}${i}`, command_type: 'ADD_NODE', payload: { target: `${prefix}-${i}`, node_kind: kind } },
    });
  }
}

function wireErrorCollectors(page: Page): string[] {
  const errs: string[] = [];
  page.on('pageerror', (e) => errs.push(`pageerror:${e.message}`));
  page.on('console', (m) => {
    if (m.type() === 'error') errs.push(`console:${m.text()}`);
  });
  return errs;
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(INIT_SCRIPT);
});

test('bootstrap: single canvas, single game socket, no errors', async ({ page }) => {
  const errs = wireErrorCollectors(page);
  const sid = await createSession(page);
  await page.goto(`${API}/game/${sid}`);
  await page.waitForSelector('canvas', { timeout: 20_000 });
  await page.waitForTimeout(1500);
  const counters = await page.evaluate(() => ({
    ...(window as unknown as { __vcCounters: { wsOpen: number; wsTotal: number } }).__vcCounters,
    canvases: document.querySelectorAll('canvas').length,
  }));
  expect(counters.canvases, 'exactly one canvas').toBe(1);
  expect(counters.wsOpen, 'at most one live game socket').toBeLessThanOrEqual(1);
  expect(errs, 'no console/page errors').toEqual([]);
});

test('50+ functional nodes render on one canvas without errors', async ({ page }) => {
  const errs = wireErrorCollectors(page);
  const sid = await createSession(page);
  await addNodes(page, sid, 'app_server', 'app', 26);
  await addNodes(page, sid, 'redis', 'cache', 14);
  await addNodes(page, sid, 'postgresql', 'db', 14); // 54 nodes total
  await page.goto(`${API}/game/${sid}`);
  await page.waitForSelector('canvas', { timeout: 20_000 });
  await page.waitForTimeout(2500);
  const canvases = await page.evaluate(() => document.querySelectorAll('canvas').length);
  const nodeListText = (await page.locator('nav[aria-label="Infrastructure nodes"]').textContent()) ?? '';
  expect(canvases, 'still one canvas at 54 nodes').toBe(1);
  // A few representative node ids should appear in the accessible node list.
  expect(nodeListText).toContain('app-0');
  expect(nodeListText).toContain('db-13');
  expect(errs, 'no errors at scale').toEqual([]);
});

test('route round-trips do not grow canvases or leak sockets', async ({ page }) => {
  const errs = wireErrorCollectors(page);
  const sid = await createSession(page);
  for (let i = 0; i < 10; i++) {
    await page.goto(`${API}/game/${sid}`);
    await page.waitForSelector('canvas', { timeout: 20_000 });
    await page.goto(`${API}/`);
    await page.waitForTimeout(150);
  }
  await page.goto(`${API}/game/${sid}`);
  await page.waitForSelector('canvas', { timeout: 20_000 });
  await page.waitForTimeout(1000);
  const counters = await page.evaluate(() => ({
    wsOpen: (window as unknown as { __vcCounters: { wsOpen: number } }).__vcCounters.wsOpen,
    canvases: document.querySelectorAll('canvas').length,
  }));
  expect(counters.canvases, 'one canvas after 10 route round-trips').toBe(1);
  expect(counters.wsOpen, 'sockets not leaking after 10 round-trips').toBeLessThanOrEqual(1);
  expect(errs).toEqual([]);
});

for (const vp of [{ w: 1440, h: 810 }, { w: 1280, h: 720 }]) {
  test(`viewport ${vp.w}x${vp.h}: board + node list usable, no errors`, async ({ page }) => {
    const errs = wireErrorCollectors(page);
    await page.setViewportSize({ width: vp.w, height: vp.h });
    const sid = await createSession(page);
    await addNodes(page, sid, 'app_server', 'app', 8);
    await page.goto(`${API}/game/${sid}`);
    await page.waitForSelector('canvas', { timeout: 20_000 });
    await page.waitForTimeout(1200);
    await expect(page.locator('nav[aria-label="Infrastructure nodes"]')).toBeVisible();
    const canvases = await page.evaluate(() => document.querySelectorAll('canvas').length);
    expect(canvases).toBe(1);
    expect(errs).toEqual([]);
  });
}
