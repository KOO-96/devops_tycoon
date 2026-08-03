/**
 * Test-only AssetLoader that returns scripted outcomes so the REAL AssetManager
 * fallback / checksum / race paths can be exercised in a real browser. Injected via
 * the AssetManager's public `loader` constructor option — this is a test CONSUMER,
 * NOT a production global hook. It is never imported by the production app entry.
 */

import { Texture } from 'pixi.js';
import {
  AssetLoadError,
  type AssetLoader,
  type AssetLoadContext,
  type LoadedAsset,
} from '../../../src/game/pixi/assets/assetLoader';
import type { AssetManifestEntry } from '../../../src/game/pixi/assets/assetTypes';

export interface LoaderCallRecord {
  assetId: string;
  assetVersion: string | undefined;
  attempt: number;
  mode: string;
  bypassCache: boolean;
}

export type Outcome =
  | { kind: 'ok'; checksum?: string }
  | { kind: 'error'; errorKind: 'network' | 'server' | 'not_found' | 'client' | 'decode' }
  | { kind: 'delay'; ms: number; then: Outcome };

/** Decides the outcome for each load call. */
export type LoaderPlan = (call: { assetId: string; mode: string; callIndex: number }) => Outcome;

/** Creates a real Pixi Texture whose destroy() is counted (for leak assertions). */
function makeCountedTexture(onDestroy: () => void): Texture {
  const canvas = document.createElement('canvas');
  canvas.width = 8;
  canvas.height = 8;
  const tex = Texture.from(canvas);
  const orig = tex.destroy.bind(tex);
  (tex as unknown as { destroy: (v?: boolean) => void }).destroy = (v?: boolean): void => {
    onDestroy();
    orig(v);
  };
  return tex;
}

const sleep = (ms: number, signal: AbortSignal): Promise<void> =>
  new Promise((resolve) => {
    if (signal.aborted) return resolve();
    const t = setTimeout(resolve, ms);
    signal.addEventListener('abort', () => {
      clearTimeout(t);
      resolve();
    }, { once: true });
  });

export class ControlledAssetLoader implements AssetLoader {
  readonly calls: LoaderCallRecord[] = [];
  textureCreates = 0;
  textureDestroys = 0;
  private callIndex = 0;

  constructor(private readonly plan: LoaderPlan) {}

  async load(entry: AssetManifestEntry, ctx: AssetLoadContext): Promise<LoadedAsset> {
    this.calls.push({
      assetId: entry.assetId,
      assetVersion: entry.assetVersion,
      attempt: ctx.attempt,
      mode: ctx.mode,
      bypassCache: ctx.bypassCache,
    });
    const outcome = this.plan({ assetId: entry.assetId, mode: ctx.mode, callIndex: this.callIndex++ });
    return this.apply(outcome, ctx);
  }

  private async apply(outcome: Outcome, ctx: AssetLoadContext): Promise<LoadedAsset> {
    if (outcome.kind === 'delay') {
      await sleep(outcome.ms, ctx.signal);
      if (ctx.signal.aborted) throw new AssetLoadError('aborted', 'aborted during delay', { retryable: false });
      return this.apply(outcome.then, ctx);
    }
    if (outcome.kind === 'error') {
      throw new AssetLoadError(outcome.errorKind, `scripted ${outcome.errorKind}`);
    }
    // ok → a real GPU-backed texture; optionally with a computed checksum.
    this.textureCreates += 1;
    const texture = makeCountedTexture(() => {
      this.textureDestroys += 1;
    });
    return outcome.checksum !== undefined ? { texture, computedChecksum: outcome.checksum } : { texture };
  }
}
