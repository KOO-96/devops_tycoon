/** Global command controls (§20): pause/resume + speed. Buttons disable while
 * their command is in flight (§22). Only supported commands are shown. */

import { useController } from '../../session/controllerContext';
import { useGameSessionStore } from '../../state/gameSessionStore';

const SPEEDS = [1, 2, 4] as const;

export function ControlBar(): JSX.Element {
  const controller = useController();
  const summary = useGameSessionStore((s) => s.summary);
  const pending = useGameSessionStore((s) => s.pending);
  const paused = summary?.paused ?? false;

  const busy = (key: string): boolean => key in pending;

  const setPaused = (next: boolean): void => {
    void controller.runCommand(next ? 'PAUSE:on' : 'PAUSE:off', 'PAUSE', { paused: next });
  };
  const setSpeed = (speed: number): void => {
    void controller.runCommand(`SET_SPEED:${speed}`, 'SET_SPEED', { speed });
  };

  return (
    <div role="group" aria-label="Simulation controls" style={{ display: 'flex', gap: '0.5rem', padding: '0.5rem 1rem' }}>
      <button
        type="button"
        aria-pressed={paused}
        disabled={busy('PAUSE:on') || busy('PAUSE:off')}
        onClick={() => setPaused(!paused)}
      >
        {paused ? '▶ Resume' : '⏸ Pause'}
      </button>
      {SPEEDS.map((speed) => (
        <button
          key={speed}
          type="button"
          aria-pressed={summary?.speed === speed}
          disabled={busy(`SET_SPEED:${speed}`)}
          onClick={() => setSpeed(speed)}
        >
          {speed}×
        </button>
      ))}
    </div>
  );
}
