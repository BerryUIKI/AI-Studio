import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { customProviders, newCustomProvider } from '../api/customProviders';

const g = globalThis as unknown as { window?: { __BERRY_SESSION__?: string } };

beforeEach(() => {
  // Short-circuit the session wrapper so it never makes an extra fetch
  // (this test file runs in the node environment, so inject a minimal window).
  g.window = { __BERRY_SESSION__: 'test-token' };
});

afterEach(() => {
  delete g.window;
  vi.unstubAllGlobals();
});

it('sends configuration and fixtures only to the local provider service', async () => {
  const fetcher = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
  vi.stubGlobal('fetch', fetcher);
  await customProviders.save(newCustomProvider(), false);
  await customProviders.fixture('custom-fixture', { width: 64 }, { data: [] });
  expect(fetcher.mock.calls.map((call) => (call as unknown[])[0])).toEqual([
    '/api/v1/custom-providers', '/api/v1/custom-providers/custom-fixture/fixture',
  ]);
  expect(JSON.stringify(fetcher.mock.calls)).not.toContain('api_key');
});

it('does not echo raw response content when an operation fails', async () => {
  const json = vi.fn(async () => ({ detail: 'sensitive-provider-error' }));
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 400, json })));
  await expect(customProviders.prepare('custom-fixture')).rejects.toThrow('HTTP 400');
  expect(json).not.toHaveBeenCalled();
});
