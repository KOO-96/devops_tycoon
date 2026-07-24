import { Link } from 'react-router-dom';

export function NotFoundPage(): JSX.Element {
  return (
    <main style={{ maxWidth: 480, margin: '4rem auto', padding: '0 1rem' }}>
      <h1>Not found</h1>
      <p>
        <Link to="/">Back to start</Link>
      </p>
    </main>
  );
}
