/**
 * Engine Connection Routing Tests (Issue #127)
 *
 * Validates frontend integration for stable connection routing:
 * - Connection ID mapping and legacy engine_id fallback
 * - Creative action requests include connection_id
 * - Lifecycle controls route by connection identity and ownership
 * - Connection registry compatibility
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useCreativeStore } from '../stores/useCreativeStore';
import { useEngineStore } from '../stores/useEngineStore';

describe('Engine Connection Routing Integration', () => {
  beforeEach(() => {
    // Reset stores before each test
    useCreativeStore.setState({
      connectionId: 'comfyui-managed',
      engineId: 'managed_comfyui',
      prompt: 'test prompt',
      isGenerating: false,
    });

    useEngineStore.setState({
      instances: [
        {
          id: 'comfyui-managed',
          type: 'comfyui',
          name: 'ComfyUI Engine',
          is_managed: true,
          is_builtin: false,
          status: 'running',
          endpoint: 'http://127.0.0.1:8188',
          capabilities: ['txt2img', 'img2img'],
          connection_id: 'comfyui-managed',
        },
        {
          id: 'webui-managed',
          type: 'webui',
          name: 'SD WebUI',
          is_managed: true,
          is_builtin: false,
          status: 'stopped',
          endpoint: 'http://127.0.0.1:7860',
          capabilities: ['txt2img', 'img2img', 'inpaint'],
          connection_id: 'webui-managed',
        },
      ],
    });

    // Mock fetch
    globalThis.fetch = vi.fn();
  });

  describe('Connection ID Mapping', () => {
    it('should map legacy engine_id to stable connection_id', () => {
      const store = useCreativeStore.getState();

      store.setEngineId('managed_comfyui');

      const state = useCreativeStore.getState();
      expect(state.engineId).toBe('managed_comfyui');
      expect(state.connectionId).toBe('comfyui-managed');
    });

    it('should map webui legacy ID correctly', () => {
      const store = useCreativeStore.getState();

      store.setEngineId('managed_webui');

      const state = useCreativeStore.getState();
      expect(state.engineId).toBe('managed_webui');
      expect(state.connectionId).toBe('webui-managed');
    });

    it('should handle direct connection_id setting', () => {
      const store = useCreativeStore.getState();

      store.setConnectionId('webui-managed');

      const state = useCreativeStore.getState();
      expect(state.connectionId).toBe('webui-managed');
    });
  });

  describe('Creative Action Request Routing', () => {
    it('should include connection_id in execute payload', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          success: true,
          task_id: 'task-123',
          asset_id: 'asset-456',
          image_url: '/image.png',
          width: 512,
          height: 512,
        }),
      });
      globalThis.fetch = mockFetch;

      const store = useCreativeStore.getState();
      store.setConnectionId('comfyui-managed');
      store.setPrompt('test prompt');
      await store.executeCreativeAction();

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/creative/execute',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: expect.stringContaining('"connection_id":"comfyui-managed"'),
        })
      );
    });

    it('should include both connection_id and legacy engine_id for backward compatibility', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          success: true,
          task_id: 'task-123',
          asset_id: 'asset-456',
          image_url: '/image.png',
          width: 512,
          height: 512,
        }),
      });
      globalThis.fetch = mockFetch;

      const store = useCreativeStore.getState();
      store.setConnectionId('webui-managed');
      store.setEngineId('managed_webui');
      store.setPrompt('test webui prompt');
      await store.executeCreativeAction();

      const callBody = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(callBody.connection_id).toBe('webui-managed');
      expect(callBody.engine_id).toBe('managed_webui');
    });

    it('should pass connection_id in img2img action', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          success: true,
          task_id: 'task-img2img',
          asset_id: 'asset-789',
          image_url: '/output.png',
          width: 512,
          height: 512,
        }),
      });
      globalThis.fetch = mockFetch;

      const store = useCreativeStore.getState();
      store.setConnectionId('comfyui-managed');
      store.setPrompt('transform this image');
      store.setReferenceImage({
        assetId: 'ref-123',
        imageUrl: '/ref.png',
        width: 512,
        height: 512,
      });
      await store.executeCreativeAction();

      const callBody = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(callBody.connection_id).toBe('comfyui-managed');
      expect(callBody.action).toBe('img2img');
      expect(callBody.input_image_id).toBe('ref-123');
    });
  });

  describe('Lifecycle Control Routing', () => {
    it('should route ComfyUI start to correct endpoint', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, status: 'started', pid: 12345 }),
      });
      globalThis.fetch = mockFetch;

      const store = useEngineStore.getState();
      await store.startEngine('comfyui-managed');

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/runtime/start', {
        method: 'POST',
      });
    });

    it('should route WebUI start to webui-specific endpoint', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, status: 'started', pid: 67890 }),
      });
      globalThis.fetch = mockFetch;

      const store = useEngineStore.getState();
      await store.startEngine('webui-managed');

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/runtime/webui/start', {
        method: 'POST',
      });
    });

    it('should prevent starting external (non-managed) engines', async () => {
      const mockFetch = vi.fn();
      globalThis.fetch = mockFetch;

      const store = useEngineStore.getState();

      // Add external connection
      store.setInstances([
        ...store.instances,
        {
          id: 'external-comfy',
          type: 'comfyui',
          name: 'External ComfyUI',
          is_managed: false,
          is_builtin: false,
          status: 'running',
          endpoint: 'http://192.168.1.100:8188',
          capabilities: ['txt2img'],
          connection_id: 'external-comfy',
        },
      ]);

      const startResult = await store.startEngine('external-comfy');

      expect(startResult.success).toBe(false);
      expect(startResult.message).toContain('External engines cannot be started');
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('should route ComfyUI stop to correct endpoint', async () => {
      const mockFetch = vi.fn().mockResolvedValue({ ok: true });
      globalThis.fetch = mockFetch;

      const store = useEngineStore.getState();
      await store.stopEngine('comfyui-managed');

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/runtime/stop', {
        method: 'POST',
      });
    });

    it('should route WebUI stop to webui-specific endpoint', async () => {
      const mockFetch = vi.fn().mockResolvedValue({ ok: true });
      globalThis.fetch = mockFetch;

      const store = useEngineStore.getState();
      await store.stopEngine('webui-managed');

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/runtime/webui/stop', {
        method: 'POST',
      });
    });
  });

  describe('Connection Registry Compatibility', () => {
    it('should use connection_id field in engine instances', () => {
      const store = useEngineStore.getState();

      const comfyInstance = store.instances.find(
        (i) => i.id === 'comfyui-managed'
      );

      expect(comfyInstance).toBeDefined();
      expect(comfyInstance?.connection_id).toBe('comfyui-managed');
      expect(comfyInstance?.type).toBe('comfyui');
    });

    it('should handle instances fetched from backend', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          instances: [
            {
              id: 'comfyui-managed',
              type: 'comfyui',
              name: 'ComfyUI Engine',
              is_managed: true,
              is_builtin: false,
              status: 'running',
              endpoint: 'http://127.0.0.1:8188',
              capabilities: ['txt2img', 'img2img'],
              connection_id: 'comfyui-managed',
            },
            {
              id: 'external-comfy-a100',
              type: 'comfyui',
              name: 'Studio ComfyUI A100',
              is_managed: false,
              is_builtin: false,
              status: 'running',
              endpoint: 'http://192.168.1.200:8188',
              capabilities: ['txt2img', 'img2img', 'workflows'],
              connection_id: 'external-comfy-a100',
            },
          ],
        }),
      });
      globalThis.fetch = mockFetch;

      const store = useEngineStore.getState();
      await store.fetchInstances();

      const state = useEngineStore.getState();
      expect(state.instances).toHaveLength(2);
      expect(state.instances[0].connection_id).toBe('comfyui-managed');
      expect(state.instances[1].connection_id).toBe('external-comfy-a100');
      expect(state.instances[1].is_managed).toBe(false);
    });
  });
});
