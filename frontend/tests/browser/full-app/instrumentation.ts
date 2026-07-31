/**
 * Test-side (Playwright) instrumentation for the full-app smoke. Injected via
 * page.addInitScript BEFORE the app loads — it wraps window.WebSocket to count live
 * sockets and exposes counters on the TEST page's window. This is NOT product code
 * and never ships in the production bundle.
 */

// IMPORTANT: only GAME sockets are counted. The Vite dev server also opens an HMR
// WebSocket (ws://host/?token=…), which is NOT a game socket — counting it would
// falsely read as "2 concurrent sockets" in dev. Game sockets match the backend WS
// path `/ws/v1/game-sessions/…`. `wsOpen` is concurrent-open (decrements on close).
export const GAME_WS_PATTERN = '/ws/v1/game-sessions';

export const INIT_SCRIPT = `
(() => {
  const w = window;
  w.__vcCounters = { wsOpen: 0, wsTotal: 0, nonGameOpen: 0 };
  const NativeWS = w.WebSocket;
  const isGame = (u) => String(u).indexOf('${GAME_WS_PATTERN}') !== -1;
  function CountingWS(url, protocols) {
    const ws = protocols === undefined ? new NativeWS(url) : new NativeWS(url, protocols);
    const game = isGame(url);
    if (game) { w.__vcCounters.wsTotal += 1; w.__vcCounters.wsOpen += 1; }
    else { w.__vcCounters.nonGameOpen += 1; }
    ws.addEventListener('close', () => {
      if (game) w.__vcCounters.wsOpen = Math.max(0, w.__vcCounters.wsOpen - 1);
    }, { once: true });
    return ws;
  }
  CountingWS.prototype = NativeWS.prototype;
  CountingWS.CONNECTING = NativeWS.CONNECTING;
  CountingWS.OPEN = NativeWS.OPEN;
  CountingWS.CLOSING = NativeWS.CLOSING;
  CountingWS.CLOSED = NativeWS.CLOSED;
  w.WebSocket = CountingWS;
})();
`;

export interface FullAppCounters {
  /** Concurrent-open GAME sockets (Vite HMR excluded). */
  wsOpen: number;
  wsTotal: number;
  /** Non-game sockets created (e.g. Vite HMR) — informational only. */
  nonGameOpen: number;
  canvases: number;
}
