/** Vite config for the TEST-ONLY asset-runtime browser harness. Separate root/entry
 * from the production app (frontend/index.html → src/main.tsx), so this harness and
 * its ControlledAssetLoader can never enter the production bundle. */

import { defineConfig } from 'vite';

export default defineConfig({
  root: __dirname,
  server: { port: 5178, strictPort: true },
  preview: { port: 5178, strictPort: true },
});
