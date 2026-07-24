/** Accessible error region (§13, §25). Shows the stable error code + message and
 * the request_id for support; never a stack trace / SQL / URL. */

import { useGameSessionStore } from '../../state/gameSessionStore';

export function ErrorRegion(): JSX.Element {
  const error = useGameSessionStore((s) => s.lastError);
  const clear = useGameSessionStore((s) => s.setError);

  return (
    <div aria-live="assertive" role="alert" style={{ minHeight: '1.5rem' }}>
      {error !== null && (
        <div className="banner banner-error">
          <strong>{error.code}</strong>: {error.message}
          {error.requestId !== '' && <small> (request {error.requestId})</small>}{' '}
          <button type="button" onClick={() => clear(null)} aria-label="Dismiss error">
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
