import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useGameSessionStore } from '../../src/state/gameSessionStore';
import { NodeList } from '../../src/components/common/NodeList';
import { ControlBar } from '../../src/components/hud/ControlBar';
import { Hud } from '../../src/components/hud/Hud';
import { ControllerProvider } from '../../src/session/controllerContext';
import type { GameSessionController } from '../../src/session/controller';
import { makeSnapshot, makeSummary } from '../helpers/factories';

function withController(controller: Partial<GameSessionController>, ui: JSX.Element) {
  return render(
    <ControllerProvider controller={controller as GameSessionController}>{ui}</ControllerProvider>,
  );
}

describe('NodeList (accessible selection)', () => {
  beforeEach(() => useGameSessionStore.getState().reset());

  it('lists nodes and toggles store selection on click', async () => {
    useGameSessionStore.setState({ snapshot: makeSnapshot() });
    render(<NodeList />);
    const btn = screen.getByRole('button', { name: /app-1/ });
    expect(btn).toHaveAttribute('aria-pressed', 'false');
    await userEvent.click(btn);
    expect(useGameSessionStore.getState().selectedNodeId).toBe('app-1');
  });
});

describe('ControlBar', () => {
  beforeEach(() => useGameSessionStore.getState().reset());

  it('sends a typed SET_SPEED command via the controller', async () => {
    useGameSessionStore.setState({ summary: makeSummary({ speed: 1 }) });
    const runCommand = vi.fn().mockResolvedValue(null);
    withController({ runCommand } as unknown as Partial<GameSessionController>, <ControlBar />);
    await userEvent.click(screen.getByRole('button', { name: '2×' }));
    expect(runCommand).toHaveBeenCalledWith('SET_SPEED:2', 'SET_SPEED', { speed: 2 });
  });

  it('disables a control while its command is pending', () => {
    useGameSessionStore.setState({
      summary: makeSummary(),
      pending: { 'SET_SPEED:4': { key: 'SET_SPEED:4', commandId: 'c', commandType: 'SET_SPEED', payload: {}, status: 'in_flight' } },
    });
    withController({ runCommand: vi.fn() } as unknown as Partial<GameSessionController>, <ControlBar />);
    expect(screen.getByRole('button', { name: '4×' })).toBeDisabled();
  });
});

describe('Hud', () => {
  beforeEach(() => useGameSessionStore.getState().reset());

  it('shows tick and incident count', () => {
    useGameSessionStore.setState({
      currentTick: 55,
      summary: makeSummary({ active_incidents: [{ type: 'OUTAGE', target: 'db-1', phase: 'active' }] }),
    });
    render(<Hud />);
    expect(screen.getByText('55')).toBeInTheDocument();
    expect(screen.getByLabelText('Game status')).toBeInTheDocument();
  });
});
