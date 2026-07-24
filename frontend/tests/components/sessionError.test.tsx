import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { SessionErrorScreen } from '../../src/components/common/SessionErrorScreen';
import { GamePage } from '../../src/pages/GamePage';
import { ControllerProvider } from '../../src/session/controllerContext';
import type { GameSessionController } from '../../src/session/controller';
import { useGameSessionStore } from '../../src/state/gameSessionStore';

describe('SessionErrorScreen', () => {
  it('not_found shows recovery CTAs and fires handlers (no retry button)', async () => {
    const onNewGame = vi.fn();
    const onBackToStart = vi.fn();
    render(
      <SessionErrorScreen
        kind="not_found"
        sessionId="abcdef12-3456-7890-abcd-ef1234567890"
        error={{ code: 'SESSION_NOT_FOUND', message: 'gone', requestId: 'req-9' }}
        onNewGame={onNewGame}
        onBackToStart={onBackToStart}
      />,
    );
    expect(screen.getByText('게임 세션을 찾을 수 없습니다.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '다시 시도' })).toBeNull();
    expect(screen.getByText(/req-9/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '새 게임 시작' }));
    await userEvent.click(screen.getByRole('button', { name: '시작 화면으로 돌아가기' }));
    expect(onNewGame).toHaveBeenCalled();
    expect(onBackToStart).toHaveBeenCalled();
  });

  it('recoverable_error shows a retry button distinct from not_found', () => {
    render(
      <SessionErrorScreen
        kind="recoverable_error"
        sessionId="s"
        error={{ code: 'DATABASE_UNAVAILABLE', message: 'down', requestId: '' }}
        onNewGame={vi.fn()}
        onBackToStart={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: '다시 시도' })).toBeInTheDocument();
    expect(screen.queryByText('게임 세션을 찾을 수 없습니다.')).toBeNull();
  });
});

describe('GamePage load gating', () => {
  beforeEach(() => useGameSessionStore.getState().reset());

  function renderGamePage() {
    const controller = {
      bootstrapSession: vi.fn().mockResolvedValue(undefined),
      teardown: vi.fn(),
      startNewGame: vi.fn().mockResolvedValue('new'),
      retry: vi.fn(),
    } as unknown as GameSessionController;
    render(
      <MemoryRouter initialEntries={['/game/s']}>
        <ControllerProvider controller={controller}>
          <Routes>
            <Route path="/game/:sessionId" element={<GamePage />} />
          </Routes>
        </ControllerProvider>
      </MemoryRouter>,
    );
    return controller;
  }

  it('renders the Not Found screen (not an empty board) when loadState=not_found', async () => {
    const controller = renderGamePage();
    // The bootstrap effect ran; simulate the controller's not_found outcome.
    useGameSessionStore.getState().setLoadState('not_found', {
      code: 'SESSION_NOT_FOUND',
      message: 'gone',
      requestId: '',
    });
    expect(await screen.findByText('게임 세션을 찾을 수 없습니다.')).toBeInTheDocument();
    expect(screen.queryByLabelText('Game status')).toBeNull(); // no HUD/board
    expect(controller.bootstrapSession).toHaveBeenCalledWith('s');
  });

  it('shows a loading state before ready', () => {
    renderGamePage();
    expect(screen.getByText('Loading game session…')).toBeInTheDocument();
  });
});
