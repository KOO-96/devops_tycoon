import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';

vi.mock('pixi.js', async () => await import('../helpers/fakePixi'));

import { AssetRuntimeProvider, useAssetManager } from '../../src/game/assetRuntimeContext';
import { AssetManager } from '../../src/game/pixi/assets/AssetManager';

const managers: AssetManager[] = [];
afterEach(async () => {
  while (managers.length) await managers.pop()!.disposeAll();
});

function Probe({ onManager }: { onManager: (m: AssetManager | null) => void }): JSX.Element {
  onManager(useAssetManager());
  return <div />;
}

describe('AssetRuntimeProvider', () => {
  it('provides an injected manager to consumers (production seam)', () => {
    const injected = new AssetManager();
    managers.push(injected);
    let seen: AssetManager | null = null;
    render(
      <AssetRuntimeProvider manager={injected}>
        <Probe onManager={(m) => (seen = m)} />
      </AssetRuntimeProvider>,
    );
    expect(seen).toBe(injected);
  });

  it('shares ONE manager instance across multiple consumers', () => {
    const injected = new AssetManager();
    managers.push(injected);
    const seen: Array<AssetManager | null> = [];
    render(
      <AssetRuntimeProvider manager={injected}>
        <Probe onManager={(m) => seen.push(m)} />
        <Probe onManager={(m) => seen.push(m)} />
      </AssetRuntimeProvider>,
    );
    expect(seen[0]).toBe(injected);
    expect(seen[1]).toBe(injected);
  });

  it('returns null outside a provider (scene falls back to a local manager)', () => {
    let seen: AssetManager | null = null;
    render(<Probe onManager={(m) => (seen = m)} />);
    expect(seen).toBeNull();
  });

  it('uninjected under StrictMode yields a usable committed manager', async () => {
    const seen: Array<AssetManager | null> = [];
    const { unmount } = render(
      <StrictMode>
        <AssetRuntimeProvider>
          <Probe onManager={(m) => seen.push(m)} />
        </AssetRuntimeProvider>
      </StrictMode>,
    );
    const live = seen[seen.length - 1];
    expect(live).toBeInstanceOf(AssetManager);
    if (live) managers.push(live);
    // The committed manager is live (not disposed) and usable.
    const h = await live!.acquire('building.redis.dev');
    expect(h.texture).not.toBeNull();
    h.release();
    unmount();
  });
});
