/**
 * Per-launch session token access for the Berry backend (F02).
 *
 * The token arrives through one of two channels:
 * - Packaged/desktop: injected into index.html as window.__BERRY_SESSION__
 *   by the backend before the page ever runs.
 * - Vite dev server: fetched from /api/v1/auth/session, which only answers
 *   trusted origins.
 */

declare global {
  interface Window {
    __BERRY_SESSION__?: string;
  }
}

let cachedToken: string | null | undefined;

async function fetchDevToken(): Promise<string | null> {
  try {
    const res = await fetch('/api/v1/auth/session');
    if (!res.ok) return null;
    const data = await res.json();
    return typeof data.session_token === 'string' && data.session_token ? data.session_token : null;
  } catch {
    return null;
  }
}

/** Resolve the session token once per page load; null when unavailable. */
export async function getSessionToken(): Promise<string | null> {
  if (cachedToken !== undefined) return cachedToken;
  const injected = typeof window !== 'undefined' ? window.__BERRY_SESSION__ : undefined;
  if (injected) {
    cachedToken = injected;
    return cachedToken;
  }
  cachedToken = await fetchDevToken();
  return cachedToken;
}

/**
 * fetch wrapper that attaches the session token for sensitive backend calls.
 * Falls back to plain fetch semantics when no token is available.
 */
export async function fetchWithSession(input: string, init: RequestInit = {}): Promise<Response> {
  const token = await getSessionToken();
  const headers = new Headers(init.headers || {});
  if (token) headers.set('X-Session-Token', token);
  return fetch(input, { ...init, headers });
}
