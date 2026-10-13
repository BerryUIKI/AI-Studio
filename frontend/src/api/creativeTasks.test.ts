import { afterEach, describe, expect, it, vi } from 'vitest';
import { observeCreativeTask } from './creativeTasks';

afterEach(() => vi.unstubAllGlobals());

describe('durable creative subscriptions', () => {
  it('falls back to the same task after a stream outage without resubmission', async () => {
    let source: MockSource;
    class MockSource {
      onmessage?: (event: MessageEvent) => void;
      onerror?: () => void;
      close = vi.fn();
      constructor(public url: string) { source = this; }
    }
    vi.stubGlobal('EventSource', MockSource);
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 'task', status: 'succeeded', outputs: {} }) });
    vi.stubGlobal('fetch', fetcher);
    const updates = observeCreativeTask('task');
    const first = updates.next();
    source!.onmessage?.({ data: JSON.stringify({ id: 'task', status: 'running' }) } as MessageEvent);
    expect((await first).value.status).toBe('running');
    source!.onerror?.();
    expect((await updates.next()).value.status).toBe('succeeded');
    await updates.next();
    expect(source!.url).toBe('/api/v1/creative/tasks/task/events');
    expect(fetcher).toHaveBeenCalledOnce();
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/creative/tasks/task');
  });
});
