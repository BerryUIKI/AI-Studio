// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type SessionModule = typeof import('../api/session');

let session: SessionModule;

beforeEach(async () => {
  vi.resetModules();
  session = await import('../api/session');
});

afterEach(() => {
  vi.unstubAllGlobals();
  delete (window as { __BERRY_SESSION__?: string }).__BERRY_SESSION__;
});

describe('session token helper', () => {
  it('prefers the injected packaged token over the dev endpoint', async () => {
    (window as { __BERRY_SESSION__?: string }).__BERRY_SESSION__ = 'injected-token';
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    await expect(session.getSessionToken()).resolves.toBe('injected-token');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('falls back to the dev endpoint when no token is injected', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ session_token: 'dev-token' }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(session.getSessionToken()).resolves.toBe('dev-token');
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/session');
  });

  it('returns null when the dev endpoint rejects the caller', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('forbidden', { status: 403 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(session.getSessionToken()).resolves.toBeNull();
  });

  it('fetchWithSession attaches the token header to requests', async () => {
    (window as { __BERRY_SESSION__?: string }).__BERRY_SESSION__ = 'header-token';
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await session.fetchWithSession('/api/v1/runtime/start', { method: 'POST' });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(headers.get('X-Session-Token')).toBe('header-token');
    expect(init.method).toBe('POST');
  });

  it('fetchWithSession preserves existing headers and merges the token', async () => {
    (window as { __BERRY_SESSION__?: string }).__BERRY_SESSION__ = 'merge-token';
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await session.fetchWithSession('/api/v1/custom-providers', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(headers.get('Content-Type')).toBe('application/json');
    expect(headers.get('X-Session-Token')).toBe('merge-token');
  });
});
