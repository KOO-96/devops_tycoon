/** Runs the REAL Python generator to stage the manifest + synthetic PNGs the browser
 * harness consumes. DRYRUN_PYTHON must point at a Python 3.11+ with tools/asset_ops. */
import { execFileSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export default function globalSetup(): void {
  const here = dirname(fileURLToPath(import.meta.url));
  const repo = resolve(here, '../../../..');
  const py = process.env.DRYRUN_PYTHON ?? resolve(repo, '.venv-ops-rv3/bin/python');
  execFileSync(py, [resolve(here, 'prepare_dryrun.py'), resolve(here, 'generated')], { stdio: 'inherit' });
}
