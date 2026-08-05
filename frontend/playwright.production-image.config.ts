/** Playwright config for the self-contained production-image browser harness. Spins up
 * its own Vite server (no backend needed) and runs the fetch/checksum/decode/fallback
 * scenarios against the real default routing AssetManager in real Chromium/WebGL2. */

import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/browser',
  testMatch: ['production-image.spec.ts'],
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5179',
    launchOptions: {
      args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'],
    },
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
  webServer: {
    command: 'vite --config tests/browser/production-image/vite.config.ts',
    port: 5179,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
