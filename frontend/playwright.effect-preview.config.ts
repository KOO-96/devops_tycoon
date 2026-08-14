/** Playwright config for the self-contained isolated effect-preview harness. Spins up
 * its own Vite server (serving frontend/public for the real effect PNG; no backend) and
 * runs the effect scenarios against the real default routing AssetManager in real WebGL2.
 * NO simulation/event wiring — asset-resource preview only. */
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/browser',
  testMatch: ['effect-preview.spec.ts'],
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5181',
    launchOptions: {
      args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'],
    },
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
  webServer: {
    command: 'vite --config tests/browser/effect-preview/vite.config.ts',
    port: 5181,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
