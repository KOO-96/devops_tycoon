/**
 * React wrapper around the Pixi scene (§18, §26). Creates the scene once, keeps
 * it in sync with the snapshot + selection, and destroys it on unmount. Guards
 * against the async `create()` resolving after the component has unmounted.
 */

import { useEffect, useRef } from 'react';
import { GameScene } from './pixi/createGameScene';
import { snapshotToBoardNodes } from './pixi/nodes';
import { useGameSessionStore } from '../state/gameSessionStore';

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
      scene.sync(snapshotToBoardNodes(snapshot), snapshot?.connections ?? []);
      scene.setSelection(selectedNodeId);
    });

    // Keep the scene in sync with store changes.
    const unsub = useGameSessionStore.subscribe((state) => {
      const scene = sceneRef.current;
      if (scene === null) return;
      scene.sync(snapshotToBoardNodes(state.snapshot), state.snapshot?.connections ?? []);
      scene.setSelection(state.selectedNodeId);
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
