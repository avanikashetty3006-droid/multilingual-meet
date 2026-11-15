/**
 * Builds WebSocket URLs for the call server without ever hard-coding localhost.
 *
 * Default: same origin as the page (wss:// on https, ws:// on http). In production nginx proxies /ws/ to the
 * call server; in dev the Vite proxy does the same. Optional override VITE_CALL_SERVER_URL (http(s)://host:port).
 */
export function wsUrl(path, override = '', loc = typeof window !== 'undefined' ? window.location : null) {
  const p = path.startsWith('/') ? path : `/${path}`;
  if (override) {
    return override.replace(/\/+$/, '').replace(/^http/, 'ws') + p;
  }
  if (!loc) throw new Error('No location available to derive the WebSocket URL');
  return `${loc.protocol === 'https:' ? 'wss:' : 'ws:'}//${loc.host}${p}`;
}
