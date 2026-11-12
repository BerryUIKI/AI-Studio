import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CreativeTaskStatus } from '../components/canvas/CreationDock';
import { useCanvasStore } from '../stores/useCanvasStore';
import { useCreativeStore } from '../stores/useCreativeStore';

describe('Creative submission ownership', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useCanvasStore.setState({ nodes: [], edges: [], past: [], future: [] });
    useCreativeStore.setState({ referenceImage: null, isGenerating: false, activeTaskId: null, cancellationRequested: false, generationNotice: null });
  });
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

  it('exposes a cancellable ID while running and preserves a late completed result', async () => {
    let completed = false;
    const fetcher = vi.fn(async (url: string) => ({ ok: true, json: async () => {
      if (url.endsWith('/submit')) return { task_id: 'task' };
      if (url.endsWith('/cancel')) return { status: 'cancel-requested', disclaimer: 'Remote work may continue and incur charges.' };
      return completed
        ? { id: 'task', status: 'succeeded', metadata: { cancel_requested: true }, outputs: { success: true, task_id: 'task', asset_id: 'output', image_url: '/api/v1/assets/output/content', width: 32, height: 24 } }
        : { id: 'task', status: 'running', metadata: {}, outputs: {} };
    } }));
    vi.stubGlobal('fetch', fetcher);
    const execution = useCreativeStore.getState().executeCreativeAction();
    await vi.advanceTimersByTimeAsync(0);
    expect(useCreativeStore.getState().activeTaskId).toBe('task');
    expect(useCreativeStore.getState().isGenerating).toBe(true);
    await vi.advanceTimersByTimeAsync(4500);
    expect(useCreativeStore.getState().generationStage).toBe('Running');
    expect(useCreativeStore.getState().generationProgress).toBe(0);
    await useCreativeStore.getState().cancelGeneration();
    expect(useCreativeStore.getState().isGenerating).toBe(true);
    const markup = renderToStaticMarkup(<CreativeTaskStatus {...useCreativeStore.getState()} />);
    expect(markup).toContain('Cancellation requested');
    expect(markup).toContain('Remote work may continue and incur charges.');
    expect(markup).not.toContain('Denoising');
    completed = true;
    await vi.advanceTimersByTimeAsync(1000);
    await execution;
    expect(useCanvasStore.getState().nodes[0].data.assetId).toBe('output');
    expect(useCreativeStore.getState().isGenerating).toBe(false);
    expect(useCreativeStore.getState().generationNotice).toContain('completed before cancellation');
    expect(fetcher.mock.calls.filter(([url]) => url.endsWith('/submit'))).toHaveLength(1);
  });
});
