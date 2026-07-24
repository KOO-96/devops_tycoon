/** Connection state (§14, §21): WebSocket + backend reachability, kept separate
 * from game data so UI can show a connection banner independently. */

import { create } from 'zustand';
import type { SocketStatus } from '../websocket/gameSessionSocket';

export type BackendStatus = 'unknown' | 'ok' | 'unreachable';

export interface ConnectionState {
  socketStatus: SocketStatus;
  backendStatus: BackendStatus;
  protocolError: string | null;
  setSocketStatus: (status: SocketStatus) => void;
  setBackendStatus: (status: BackendStatus) => void;
  setProtocolError: (message: string | null) => void;
  reset: () => void;
}

const initial = {
  socketStatus: 'idle' as SocketStatus,
  backendStatus: 'unknown' as BackendStatus,
  protocolError: null as string | null,
};

export const useConnectionStore = create<ConnectionState>((set) => ({
  ...initial,
  setSocketStatus: (socketStatus) => set({ socketStatus }),
  setBackendStatus: (backendStatus) => set({ backendStatus }),
  setProtocolError: (protocolError) => set({ protocolError }),
  reset: () => set({ ...initial }),
}));
