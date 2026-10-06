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

  describe('fetchEngineConfig', () => {
    it('fetches engine configuration and updates instance port and extra_args', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          instance_id: 'comfyui-managed',
          engine_type: 'comfyui',
          port: 8199,
          extra_args: ['--lowvram', '--fast'],
          is_running: false,
          restart_required: false,
        }),
      });

      const store = useEngineStore.getState();
      const config = await store.fetchEngineConfig('comfyui-managed');

      expect(config).not.toBeNull();
      expect(config?.port).toBe(8199);
      expect(config?.extra_args).toEqual(['--lowvram', '--fast']);

      const updated = useEngineStore.getState().instances.find((i) => i.id === 'comfyui-managed');
      expect(updated?.port).toBe(8199);
      expect(updated?.extra_args).toEqual(['--lowvram', '--fast']);
      expect(updated?.endpoint).toBe('http://127.0.0.1:8199');
    });

    it('handles fetch error gracefully and returns null', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
      });

      const store = useEngineStore.getState();
      const config = await store.fetchEngineConfig('unknown-engine');

      expect(config).toBeNull();
    });
  });

  describe('saveEngineConfig', () => {
    it('saves engine configuration and updates instance state and endpoint', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          success: true,
          message: 'Engine configuration updated successfully.',
          requires_restart: false,
          config: {
            instance_id: 'comfyui-managed',
            engine_type: 'comfyui',
            port: 8288,
            extra_args: ['--medvram'],
            is_running: false,
            restart_required: false,
          },
        }),
      });

      const store = useEngineStore.getState();
      const result = await store.saveEngineConfig('comfyui-managed', {
        port: 8288,
        extraArgs: ['--medvram'],
      });

      expect(result.success).toBe(true);
      expect(result.requires_restart).toBe(false);

      const updated = useEngineStore.getState().instances.find((i) => i.id === 'comfyui-managed');
      expect(updated?.port).toBe(8288);
      expect(updated?.extra_args).toEqual(['--medvram']);
      expect(updated?.endpoint).toBe('http://127.0.0.1:8288');
    });

    it('returns requires_restart when saving configuration for a running engine', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          success: true,
          message: 'Engine configuration saved. Engine restart is required for changes to take effect.',
          requires_restart: true,
          config: {
            instance_id: 'comfyui-managed',
            engine_type: 'comfyui',
            port: 8388,
            extra_args: ['--lowvram'],
            is_running: true,
            restart_required: true,
          },
        }),
      });

      const store = useEngineStore.getState();
      const result = await store.saveEngineConfig('comfyui-managed', {
        port: 8388,
        extraArgs: ['--lowvram'],
      });

      expect(result.success).toBe(true);
      expect(result.requires_restart).toBe(true);
      expect(result.message).toContain('restart is required');
    });

    it('handles backend validation error (e.g. port conflict or invalid range) without updating instance', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({
          detail: 'Port 7860 is already in use by engine webui-managed (port 7860)',
        }),
      });

      const store = useEngineStore.getState();
      const originalInstance = useEngineStore.getState().instances.find((i) => i.id === 'comfyui-managed');
      const originalPort = originalInstance?.port;

      const result = await store.saveEngineConfig('comfyui-managed', {
        port: 7860,
        extraArgs: ['--lowvram'],
      });

      expect(result.success).toBe(false);
      expect(result.message).toContain('Port 7860 is already in use');

      const afterAttempt = useEngineStore.getState().instances.find((i) => i.id === 'comfyui-managed');
      expect(afterAttempt?.port).toBe(originalPort);
    });

    it('handles network failure cleanly', async () => {
      globalThis.fetch = vi.fn().mockRejectedValue(new Error('Network connection refused'));

      const store = useEngineStore.getState();
      const result = await store.saveEngineConfig('comfyui-managed', {
        port: 9000,
        extraArgs: [],
      });

      expect(result.success).toBe(false);
      expect(result.message).toContain('Network connection refused');
    });
  });
});
