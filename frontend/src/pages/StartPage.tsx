/** Start screen: create a new game session (§8). */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useController } from '../session/controllerContext';
import { ApiError } from '../api/errors';

export function StartPage(): JSX.Element {
  const controller = useController();
  const navigate = useNavigate();
  const [seed, setSeed] = useState(1);
  const [users, setUsers] = useState(100);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = async (): Promise<void> => {
    setBusy(true);
    setError(null);
    try {
      const sessionId = await controller.startNewGame({ seed, users });
      navigate(`/game/${sessionId}`);
    } catch (err) {
      setError(err instanceof ApiError ? `${err.code}: ${err.message}` : 'Could not start game.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main style={{ maxWidth: 480, margin: '4rem auto', padding: '0 1rem' }}>
      <h1>DevOps Tycoon</h1>
      <p>Build and operate a resilient system. Create a new game to begin.</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void start();
        }}
      >
        <p>
          <label>
            Seed{' '}
            <input
              type="number"
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value))}
              aria-label="Simulation seed"
            />
          </label>
        </p>
        <p>
          <label>
            Starting users{' '}
            <input
              type="number"
              min={0}
              value={users}
              onChange={(e) => setUsers(Number(e.target.value))}
              aria-label="Starting users"
            />
          </label>
        </p>
        <button type="submit" disabled={busy}>
          {busy ? 'Creating…' : 'New game'}
        </button>
      </form>
      <p aria-live="assertive" role="alert">
        {error !== null && <span className="banner banner-error">{error}</span>}
      </p>
      <p style={{ color: '#8a97a8', fontSize: '0.8rem' }}>
        Development foundation — no authentication yet. The session id is not a
        security boundary.
      </p>
    </main>
  );
}
