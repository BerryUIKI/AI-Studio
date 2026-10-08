import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useCanvasStore } from '../stores/useCanvasStore';

class FakeSocket {
  static instances: FakeSocket[] = [];
  sent: Record<string, unknown>[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  constructor() { FakeSocket.instances.push(this); }
  send(value: string) { this.sent.push(JSON.parse(value)); }
  close() { this.onclose?.(); }
  emit(value: Record<string, unknown>) { this.onmessage?.({ data: JSON.stringify(value) } as MessageEvent); }
}

describe('Workflow subscriptions', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeSocket.instances = [];
    vi.stubGlobal('window', { location: { protocol: 'http:', host: 'localhost:8000' } });
    vi.stubGlobal('WebSocket', FakeSocket);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }));
    useCanvasStore.setState({ nodes: [{ id: 'text', type: 'workflowNode', position: { x: 0, y: 0 },
      data: { definition: { type: 'input.text', title: 'Text', category: 'input', description: '', inputs: [], outputs: [], parameters: [] }, params: { value: 'hello' }, status: 'idle' } }],
      edges: [], currentRunId: null, isExecuting: false });
  });
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

  it('submits once and reconnects with the last observed sequence', async () => {
    await useCanvasStore.getState().runWorkflow();
    const runId = useCanvasStore.getState().currentRunId;
    const first = FakeSocket.instances[0];
    first.onopen?.();
    expect(first.sent[0]).toEqual({ type: 'SUBSCRIBE', run_id: runId, after_sequence: 0 });
    first.emit({ type: 'NODE_STATUS', run_id: runId, sequence: 3, node_id: 'text', status: 'running' });
    first.close();
    await vi.advanceTimersByTimeAsync(1000);
    const resumed = FakeSocket.instances[1];
    resumed.onopen?.();
    expect(resumed.sent[0]).toEqual({ type: 'SUBSCRIBE', run_id: runId, after_sequence: 3 });
    expect(fetch).toHaveBeenCalledTimes(1);
    resumed.emit({ type: 'GRAPH_FINISHED', run_id: runId, sequence: 4, status: 'completed' });
    expect(useCanvasStore.getState().isExecuting).toBe(false);
    await vi.advanceTimersByTimeAsync(30000);
    expect(resumed.sent).toHaveLength(1); // No unmatched application PING protocol.
  });

  it('ignores stale events and cleanup from an obsolete run', async () => {
    await useCanvasStore.getState().runWorkflow();
    const oldId = useCanvasStore.getState().currentRunId;
    const old = FakeSocket.instances[0];
    await vi.advanceTimersByTimeAsync(1);
    await useCanvasStore.getState().runWorkflow();
    const currentId = useCanvasStore.getState().currentRunId;
    expect(currentId).not.toBe(oldId);
    old.emit({ type: 'NODE_OUTPUT', run_id: oldId, sequence: 1, node_id: 'text', output: { text: 'obsolete' } });
    old.emit({ type: 'GRAPH_FINISHED', run_id: oldId, sequence: 2, status: 'completed' });
    old.close();
    expect(useCanvasStore.getState().currentRunId).toBe(currentId);
    expect(useCanvasStore.getState().nodes[0].data.output).toBeUndefined();
    expect(useCanvasStore.getState().isExecuting).toBe(true);
  });
});
