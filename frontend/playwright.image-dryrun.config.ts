/** Playwright config for the P4 image dry-run harness: stages the generator output via
 * global-setup, serves it over HTTP, and proves the real app consumes+renders it. */
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/browser',
  testMatch: ['image-dryrun.spec.ts'],
  globalSetup: './tests/browser/image-dryrun/global-setup.ts',
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5180',
    launchOptions: { args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'] },
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
  webServer: {
    command: 'vite --config tests/browser/image-dryrun/vite.config.ts',
    port: 5180,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
