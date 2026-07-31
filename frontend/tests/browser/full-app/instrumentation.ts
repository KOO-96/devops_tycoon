/**
 * Test-side (Playwright) instrumentation for the full-app smoke. Injected via
 * page.addInitScript BEFORE the app loads — it wraps window.WebSocket to count live
 * sockets and exposes counters on the TEST page's window. This is NOT product code
 * and never ships in the production bundle.
 */

export const INIT_SCRIPT = `
(() => {
  const w = window;
  w.__vcCounters = { wsOpen: 0, wsTotal: 0 };
  const NativeWS = w.WebSocket;
  function CountingWS(url, protocols) {
    const ws = protocols === undefined ? new NativeWS(url) : new NativeWS(url, protocols);
    w.__vcCounters.wsTotal += 1;
    w.__vcCounters.wsOpen += 1;
    const dec = () => { w.__vcCounters.wsOpen = Math.max(0, w.__vcCounters.wsOpen - 1); };
    ws.addEventListener('close', dec, { once: true });
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
  wsOpen: number;
  wsTotal: number;
  canvases: number;
}
