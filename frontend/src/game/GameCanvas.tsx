/**
 * React wrapper around the Pixi scene (§18, §26). Creates the scene once, keeps
 * it in sync with the snapshot + selection, and destroys it on unmount. Guards
 * against the async `create()` resolving after the component has unmounted.
 */

import { useEffect, useRef } from 'react';
import { GameScene } from './pixi/createGameScene';
import { snapshotToBoardNodes } from './pixi/nodes';
import { useAssetManager } from './assetRuntimeContext';
import { useGameSessionStore } from '../state/gameSessionStore';
import type { IncidentSummary, SimulationSnapshot } from '../api/schemas';

/** Sync the scene from a snapshot, isolating any Pixi render error so it can
 * never break the zustand notification chain (which would block React's own
 * store-subscribed re-render). Errors are logged, not thrown (§24). */
function syncScene(
  scene: GameScene,
  snapshot: SimulationSnapshot | null,
  selectedNodeId: string | null,
  incidents: IncidentSummary[],
): void {
  try {
    scene.sync(snapshotToBoardNodes(snapshot), snapshot?.connections ?? []);
    scene.setSelection(selectedNodeId);
    scene.setIncidents(incidents);
  } catch (err) {
    // eslint-disable-next-line no-console
    if (import.meta.env.DEV) console.error('[GameCanvas] scene sync failed:', err);
  }
}

export function GameCanvas(): JSX.Element {
  const hostRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<GameScene | null>(null);
  const select = useGameSessionStore((s) => s.select);
  const assets = useAssetManager();

  useEffect(() => {
    const host = hostRef.current;
    if (host === null) return;
    let cancelled = false;

    // Inject the app-scoped manager when present; the scene falls back to a local
    // one otherwise (older callers / isolated tests).
    const createOptions = assets
      ? { onSelect: (id: string | null) => select(id), assets }
      : { onSelect: (id: string | null) => select(id) };

    void GameScene.create(host, createOptions).then((scene) => {
      if (cancelled) {
        scene.destroy();
        return;
      }
      sceneRef.current = scene;
      // Prime with current store state.
      const { snapshot, selectedNodeId, summary } = useGameSessionStore.getState();
      syncScene(scene, snapshot, selectedNodeId, summary?.active_incidents ?? []);
    });

    // Keep the scene in sync with store changes.
    const unsub = useGameSessionStore.subscribe((state) => {
      const scene = sceneRef.current;
      if (scene === null) return;
      syncScene(scene, state.snapshot, state.selectedNodeId, state.summary?.active_incidents ?? []);
    });

    return () => {
      cancelled = true;
      unsub();
      sceneRef.current?.destroy();
      sceneRef.current = null;
    };
  }, [select, assets]);

  return (
    <div
      ref={hostRef}
      className="canvas-host"
      role="img"
      aria-label="Isometric infrastructure board. Use the Nodes list for keyboard access."
    />
  );
}
