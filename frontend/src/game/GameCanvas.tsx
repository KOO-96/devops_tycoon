/**
 * React wrapper around the Pixi scene (§18, §26). Creates the scene once, keeps
 * it in sync with the snapshot + selection, and destroys it on unmount. Guards
 * against the async `create()` resolving after the component has unmounted.
 */

import { useEffect, useRef } from 'react';
import { GameScene } from './pixi/createGameScene';
import { snapshotToBoardNodes } from './pixi/nodes';
import { useGameSessionStore } from '../state/gameSessionStore';
import type { SimulationSnapshot } from '../api/schemas';

/** Sync the scene from a snapshot, isolating any Pixi render error so it can
 * never break the zustand notification chain (which would block React's own
 * store-subscribed re-render). Errors are logged, not thrown (§24). */
function syncScene(scene: GameScene, snapshot: SimulationSnapshot | null, selectedNodeId: string | null): void {
  try {
    scene.sync(snapshotToBoardNodes(snapshot), snapshot?.connections ?? []);
    scene.setSelection(selectedNodeId);
  } catch (err) {
    // eslint-disable-next-line no-console
    if (import.meta.env.DEV) console.error('[GameCanvas] scene sync failed:', err);
  }
}

export function GameCanvas(): JSX.Element {
  const hostRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<GameScene | null>(null);
  const select = useGameSessionStore((s) => s.select);

  useEffect(() => {
    const host = hostRef.current;
    if (host === null) return;
    let cancelled = false;

    void GameScene.create(host, { onSelect: (id) => select(id) }).then((scene) => {
      if (cancelled) {
        scene.destroy();
        return;
      }
      sceneRef.current = scene;
      // Prime with current store state.
      const { snapshot, selectedNodeId } = useGameSessionStore.getState();
      syncScene(scene, snapshot, selectedNodeId);
    });

    // Keep the scene in sync with store changes.
    const unsub = useGameSessionStore.subscribe((state) => {
      const scene = sceneRef.current;
      if (scene === null) return;
      syncScene(scene, state.snapshot, state.selectedNodeId);
    });

    return () => {
      cancelled = true;
      unsub();
      sceneRef.current?.destroy();
      sceneRef.current = null;
    };
  }, [select]);

  return (
    <div
      ref={hostRef}
      className="canvas-host"
      role="img"
      aria-label="Isometric infrastructure board. Use the Nodes list for keyboard access."
    />
  );
}
