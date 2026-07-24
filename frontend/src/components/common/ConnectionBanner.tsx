/** Backend + WebSocket connection status banner (§14, §20). */

import { useConnectionStore } from '../../state/connectionStore';

const SOCKET_LABEL: Record<string, string> = {
  idle: 'Idle',
  connecting: 'Connecting…',
  connected: 'Live',
  reconnecting: 'Reconnecting…',
  disconnected: 'Disconnected',
  failed: 'Connection failed',
};

export function ConnectionBanner(): JSX.Element {
  const socketStatus = useConnectionStore((s) => s.socketStatus);
  const backendStatus = useConnectionStore((s) => s.backendStatus);
  const protocolError = useConnectionStore((s) => s.protocolError);

  const bad =
    protocolError !== null ||
    socketStatus === 'failed' ||
    socketStatus === 'disconnected' ||
    backendStatus === 'unreachable';
  const warn = socketStatus === 'reconnecting' || socketStatus === 'connecting';
  const cls = bad ? 'banner banner-error' : warn ? 'banner banner-warn' : 'banner banner-ok';

  return (
    <div className={cls} role="status" aria-live="polite">
      <span>WebSocket: {SOCKET_LABEL[socketStatus] ?? socketStatus}</span>
      {' · '}
      <span>Backend: {backendStatus}</span>
      {protocolError !== null && <span> · {protocolError}</span>}
      {(socketStatus === 'disconnected' || socketStatus === 'failed') && (
        <span> · a disconnect is not data loss; reconnect to recover events</span>
      )}
    </div>
  );
}
