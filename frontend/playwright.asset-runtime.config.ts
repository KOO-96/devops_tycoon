/** Playwright config for the self-contained asset-runtime browser harness. Spins up
 * its own Vite server (no backend needed) and runs the fallback/checksum/race
 * scenarios against the real AssetManager in real Chromium/WebGL2. */

import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/browser',
  testMatch: ['asset-runtime.spec.ts'],
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5178',
    launchOptions: {
      // SwiftShader gives a real (software) WebGL2 context in headless CI.
      args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'],
    },
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
  webServer: {
    command: 'vite --config tests/browser/asset-runtime/vite.config.ts',
    port: 5178,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
