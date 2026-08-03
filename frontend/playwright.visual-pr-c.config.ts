/** Playwright config for the FULL-APP Visual PR C browser smoke. Assumes the app
 * stack is already running (FastAPI :8000 + Vite dev proxying to it) — bring-up steps
 * are in docs/operations/visual-pr-c-live-verification.md. Point it at the dev URL via
 * VISUAL_C_BASE_URL (default http://localhost:5173). No backend/CI is added here. */

import { defineConfig } from '@playwright/test';

const baseURL = process.env.VISUAL_C_BASE_URL ?? 'http://localhost:5173';

export default defineConfig({
  testDir: './tests/browser/full-app',
  testMatch: ['visualPrC.spec.ts'],
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL,
    launchOptions: {
      args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'],
    },
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
