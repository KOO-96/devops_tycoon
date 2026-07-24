/** Start screen: create a new game session (§8, §16). */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useController } from '../session/controllerContext';
import { ApiError } from '../api/errors';
import { PixelButton } from '../components/ui/PixelButton';

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
    <main className="start-page">
      <p className="brand" style={{ textAlign: 'center', marginBottom: 'var(--s-16)' }}>
        DevOps <span style={{ color: 'var(--c-interactive)' }}>Tycoon</span>
      </p>
      <div className="start-card">
        <h1 style={{ fontSize: 'var(--fs-heading)', marginBottom: 'var(--s-8)' }}>New game</h1>
        <p style={{ color: 'var(--c-text-secondary)', marginBottom: 'var(--s-16)' }}>
          Build and operate a resilient system. Create a new game to begin.
        </p>
        <form
          className="stack"
          onSubmit={(e) => {
            e.preventDefault();
            void start();
          }}
        >
          <label className="metric">
            <span className="metric-label">Seed</span>
            <input
              type="number"
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value))}
              aria-label="Simulation seed"
            />
          </label>
          <label className="metric">
            <span className="metric-label">Starting users</span>
            <input
              type="number"
              min={0}
              value={users}
              onChange={(e) => setUsers(Number(e.target.value))}
              aria-label="Starting users"
            />
          </label>
          <PixelButton type="submit" variant="primary" disabled={busy}>
            {busy ? 'Creating…' : 'New game'}
          </PixelButton>
        </form>
        <p aria-live="assertive" role="alert" style={{ marginTop: 'var(--s-12)' }}>
          {error !== null && <span className="banner banner-error">{error}</span>}
        </p>
      </div>
      <p style={{ color: 'var(--c-text-muted-solid)', fontSize: 'var(--fs-label)', marginTop: 'var(--s-12)' }}>
        Development foundation — no authentication yet. The session id is not a security
        boundary.
      </p>
    </main>
  );
}
