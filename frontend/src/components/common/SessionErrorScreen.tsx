/**
 * Recovery screens for a failed session bootstrap (§10–§12). Never renders an
 * empty game board — each state explains the situation and offers next actions.
 */

import type { LoadState, UiError } from '../../state/gameSessionStore';
import { PixelButton } from '../ui/PixelButton';

export interface SessionErrorScreenProps {
  kind: Extract<LoadState, 'not_found' | 'recoverable_error' | 'fatal_error'>;
  sessionId: string | null;
  error: UiError | null;
  onNewGame: () => void;
  onBackToStart: () => void;
  onRetry?: () => void;
}

function shortId(id: string | null): string {
  if (!id) return '(unknown)';
  return id.length > 12 ? `${id.slice(0, 8)}…${id.slice(-4)}` : id;
}

const COPY: Record<SessionErrorScreenProps['kind'], { title: string; body: string }> = {
  not_found: {
    title: '게임 세션을 찾을 수 없습니다.',
    body: 'The requested game session does not exist or has expired.',
  },
  recoverable_error: {
    title: '서버에 일시적으로 연결할 수 없습니다.',
    body: 'The server is temporarily unavailable. Your game may still exist — try again.',
  },
  fatal_error: {
    title: '이 세션을 열 수 없습니다.',
    body: 'This client is not compatible with the session state, or an unrecoverable error occurred.',
  },
};

export function SessionErrorScreen({
  kind,
  sessionId,
  error,
  onNewGame,
  onBackToStart,
  onRetry,
}: SessionErrorScreenProps): JSX.Element {
  const copy = COPY[kind];
  return (
    <main className="state-screen" role="alert" aria-live="assertive">
      <div className="state-card">
        <h1 style={{ fontSize: 'var(--fs-display)' }}>{copy.title}</h1>
        <p style={{ color: 'var(--c-text-secondary)' }}>{copy.body}</p>
        <p style={{ color: 'var(--c-text-muted-solid)', fontSize: 'var(--fs-label)' }}>
          Session: <code>{shortId(sessionId)}</code>
          {error?.code ? ` · ${error.code}` : ''}
        </p>
        <div className="cluster" style={{ marginTop: 'var(--s-16)' }}>
          {kind === 'recoverable_error' && onRetry && (
            <PixelButton onClick={onRetry}>다시 시도</PixelButton>
          )}
          <PixelButton variant="primary" onClick={onNewGame}>
            새 게임 시작
          </PixelButton>
          <PixelButton onClick={onBackToStart}>시작 화면으로 돌아가기</PixelButton>
        </div>
        {error?.requestId ? (
          <p style={{ color: 'var(--c-text-muted-solid)', fontSize: 'var(--fs-label)', marginTop: 'var(--s-16)' }}>
            Support reference: <code>{error.requestId}</code>
          </p>
        ) : null}
      </div>
    </main>
  );
}
