/** Vite config for the TEST-ONLY production-image browser harness. Separate root/entry
 * from the production app so the harness never enters the production bundle. */

import { defineConfig } from 'vite';

export default defineConfig({
  root: __dirname,
  server: { port: 5179, strictPort: true },
  preview: { port: 5179, strictPort: true },
});
