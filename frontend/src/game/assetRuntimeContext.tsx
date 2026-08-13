/**
 * App-scoped AssetManager provider (FE-ART-003-FU-001/003). Creates ONE manager
 * for the whole runtime, shares it across scenes/routes/sessions, and disposes it
 * only at app teardown. In dev it resets a stale manager across HMR so old textures
 * and promises don't accumulate; production has no HMR reset path.
 *
 * The manager is injectable (tests pass their own instance) — it is NOT a hidden
 * module singleton, and it holds no session/user state.
 */

import { createContext, useContext, useEffect, useRef, type ReactNode } from 'react';
import { AssetManager } from './pixi/assets/AssetManager';
import { buildProductionManifest } from './pixi/assets/generatedBuildingAsset';

const AssetRuntimeContext = createContext<AssetManager | null>(null);

// Dev-only HMR slot: survives module replacement so we can dispose the previous
// manager instead of leaking it. Never used in production builds.
interface HmrSlot {
  manager: AssetManager | null;
}
function hmrSlot(): HmrSlot | null {
  if (!import.meta.env.DEV) return null;
  const hot = (import.meta as unknown as { hot?: { data?: Record<string, unknown> } }).hot;
  const data = hot?.data;
  if (!data) return null; // no HMR data channel (e.g. test runner) → no slot
  if (!data.assetRuntime) data.assetRuntime = { manager: null } satisfies HmrSlot;
  return data.assetRuntime as HmrSlot;
}

export function AssetRuntimeProvider({
  children,
  manager,
}: {
  children: ReactNode;
  manager?: AssetManager;
}): JSX.Element {
  const ref = useRef<AssetManager | null>(null);
  if (ref.current === null) {
    if (manager) {
      ref.current = manager;
    } else {
      const slot = hmrSlot();
      // Reuse (and reset) a manager left over from a previous HMR cycle.
      const prior = slot?.manager ?? null;
      // Real app uses the PRODUCTION manifest (app_server = first production image asset);
      // the generated fallback chain still covers a load failure.
      const created = new AssetManager({ registerDevelopmentManifest: false });
      created.registerManifest(buildProductionManifest());
      if (prior) void prior.disposeAll();
      ref.current = created;
      if (slot) slot.manager = created;
    }
  }

  useEffect(() => {
    const created = ref.current;
    return () => {
      // Only dispose a manager we created (an injected one is owned by the caller).
      // In dev, leave it in the HMR slot for the next cycle to reset instead.
      if (created && !manager && !import.meta.env.DEV) void created.disposeAll();
    };
  }, [manager]);

  return <AssetRuntimeContext.Provider value={ref.current}>{children}</AssetRuntimeContext.Provider>;
}

/** Access the app-scoped AssetManager. Returns null outside a provider (callers
 * fall back to a scene-owned manager). */
export function useAssetManager(): AssetManager | null {
  return useContext(AssetRuntimeContext);
}
