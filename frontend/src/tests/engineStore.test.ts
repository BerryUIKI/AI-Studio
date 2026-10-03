import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useEngineStore, defaultBuiltinInstances } from '../stores/useEngineStore';

describe('useEngineStore', () => {
  beforeEach(() => {
    useEngineStore.setState({
      instances: defaultBuiltinInstances,
      isLoading: false,
      error: null,
      searchQuery: '',
    });
    vi.restoreAllMocks();
  });

  it('initializes with default builtin instances', () => {
    const state = useEngineStore.getState();
    expect(state.instances.length).toBeGreaterThanOrEqual(4);
    expect(state.instances.some((i) => i.id === 'builtin-canvas')).toBe(true);
    expect(state.instances.some((i) => i.id === 'comfyui-managed')).toBe(true);
    expect(state.instances.some((i) => i.id === 'webui-managed')).toBe(true);
    expect(state.instances.some((i) => i.id === 'builtin-agents')).toBe(true);
  });

  it('updates search query', () => {
    const store = useEngineStore.getState();
    store.setSearchQuery('comfy');
    expect(useEngineStore.getState().searchQuery).toBe('comfy');
  });

  it('updates instances from fetchInstances API call', async () => {
    const mockInstances = [
      {
        id: 'test-canvas',
        type: 'canvas',
        name: 'Test Canvas',
        is_managed: true,
        is_builtin: true,
        status: 'ready',
        capabilities: ['txt2img'],
      },
    ];

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ instances: mockInstances }),
    });

    const store = useEngineStore.getState();
    await store.fetchInstances();

    const state = useEngineStore.getState();
    expect(state.instances.length).toBe(1);
    expect(state.instances[0].id).toBe('test-canvas');
  });

  it('starts engine and updates status on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, message: 'ComfyUI started', pid: 1234 }),
    });

    const store = useEngineStore.getState();
    const result = await store.startEngine('comfyui-managed');

    expect(result.success).toBe(true);
    const updated = useEngineStore.getState().instances.find((i) => i.id === 'comfyui-managed');
    expect(updated?.status).toBe('running');
    expect(updated?.pid).toBe(1234);
  });

  it('marks instance as not_installed when start returns NOT_INSTALLED', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: false,
        code: 'NOT_INSTALLED',
        message: 'ComfyUI is not installed in runtime directory. Run installer first.',
      }),
    });

    const store = useEngineStore.getState();
    const result = await store.startEngine('comfyui-managed');

    expect(result.success).toBe(false);
    expect(result.code).toBe('NOT_INSTALLED');
    const updated = useEngineStore.getState().instances.find((i) => i.id === 'comfyui-managed');
    expect(updated?.status).toBe('not_installed');
  });

  it('stops engine and updates status on success', async () => {
    // Set comfyui to running first
    useEngineStore.setState((state) => ({
      instances: state.instances.map((i) =>
        i.id === 'comfyui-managed' ? { ...i, status: 'running' } : i
      ),
    }));

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'stopped' }),
    });

    const store = useEngineStore.getState();
    const success = await store.stopEngine('comfyui-managed');

    expect(success).toBe(true);
    const updated = useEngineStore.getState().instances.find((i) => i.id === 'comfyui-managed');
    expect(updated?.status).toBe('stopped');
  });
});
