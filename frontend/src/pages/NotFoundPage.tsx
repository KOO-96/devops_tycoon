import { Link } from 'react-router-dom';

export function NotFoundPage(): JSX.Element {
  return (
    <main className="state-screen">
      <div className="state-card">
        <h1 style={{ fontSize: 'var(--fs-display)' }}>Page not found</h1>
        <p style={{ color: 'var(--c-text-secondary)' }}>
          <Link to="/">Back to start</Link>
        </p>
      </div>
    </main>
  );
}
