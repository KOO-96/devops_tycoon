/**
 * Runtime config. Same-origin by default; the Vite dev server proxies /api and
 * /ws to the backend (see vite.config.ts). Production wiring is deferred.
 *
 * NOTE (§23): there is NO authentication here — this is a development Foundation,
 * not a production-ready security model. Never hard-code tokens.
 */

import type { WebSocketFactory } from './websocket/gameSessionSocket';

function wsOrigin(): string {
  if (typeof window === 'undefined') return 'ws://localhost:8000';
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}`;
}

export const config = {
  baseUrl: '',
  baseWsUrl: wsOrigin(),
};

/** Browser WebSocket factory (injectable elsewhere for tests). */
export const browserWebSocketFactory: WebSocketFactory = (url) =>
  new WebSocket(url) as unknown as ReturnType<WebSocketFactory>;
