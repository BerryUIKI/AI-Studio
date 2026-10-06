import { create } from 'zustand';

export interface EngineInstance {
  id: string;
  type: 'canvas' | 'comfyui' | 'webui' | 'agents' | 'custom' | string;
  name: string;
  version?: string | null;
  is_managed: boolean;
  is_builtin: boolean;
  install_path?: string | null;
  status: 'ready' | 'running' | 'stopped' | 'not_installed' | 'error' | 'updating';
  endpoint?: string | null;
  pid?: number | null;
  vram_used_mb?: number | null;
  capabilities: string[];
  connection_id?: string;  // Stable backend connection ID (e.g., "comfyui-managed", "webui-managed")
  port?: number | null;
  extra_args?: string[];
}

export interface StartEngineResult {
  success: boolean;
  code?: 'NOT_INSTALLED' | 'ENV_MISSING' | 'ALREADY_RUNNING' | string;
  message?: string;
  pid?: number | null;
}

export interface SaveEngineConfigResult {
  success: boolean;
  message?: string;
  requires_restart?: boolean;
}

interface EngineState {
  instances: EngineInstance[];
  isLoading: boolean;
  error: string | null;
  searchQuery: string;

  setSearchQuery: (query: string) => void;
  setInstances: (instances: EngineInstance[]) => void;
  fetchInstances: () => Promise<void>;
  fetchEngineConfig: (instanceId: string) => Promise<{ port: number; extra_args: string[] } | null>;
  saveEngineConfig: (
    instanceId: string,
    config: { port: number; extraArgs: string[] }
  ) => Promise<SaveEngineConfigResult>;
  startEngine: (instanceId: string) => Promise<StartEngineResult>;
  stopEngine: (instanceId: string) => Promise<boolean>;
}

export const defaultBuiltinInstances: EngineInstance[] = [
  {
    id: 'builtin-canvas',
    type: 'canvas',
    name: 'Infinite Canvas',
    version: 'Built-in · v0.1.0',
    is_managed: true,
    is_builtin: true,
    install_path: null,
    status: 'ready',
    endpoint: null,
    capabilities: ['txt2img', 'img2img', 'inpaint', 'upscale', 'video'],
  },
  {
    id: 'comfyui-managed',
    type: 'comfyui',
    name: 'ComfyUI Engine',
    version: 'Local · v0.3.8',
    is_managed: true,
    is_builtin: false,
    install_path: null,
    status: 'stopped',
    endpoint: 'http://127.0.0.1:8188',
    port: 8188,
    extra_args: [],
    capabilities: ['txt2img', 'img2img', 'workflows'],
    connection_id: 'comfyui-managed',
  },
  {
    id: 'webui-managed',
    type: 'webui',
    name: 'SD WebUI',
    version: 'Local · Automatic1111',
    is_managed: true,
    is_builtin: false,
    install_path: null,
    status: 'stopped',
    endpoint: 'http://127.0.0.1:7860',
    port: 7860,
    extra_args: [],
    capabilities: ['txt2img', 'img2img', 'inpaint'],
    connection_id: 'webui-managed',
  },
  {
    id: 'builtin-agents',
    type: 'agents',
    name: 'AI Agents Studio',
    version: 'Built-in · Multi-Agent',
    is_managed: true,
    is_builtin: true,
    install_path: null,
    status: 'ready',
    endpoint: null,
    capabilities: ['workflows', 'repair', 'conversational'],
  },
];

export const useEngineStore = create<EngineState>((set, get) => ({
  instances: defaultBuiltinInstances,
  isLoading: false,
  error: null,
  searchQuery: '',

  setSearchQuery: (query: string) => set({ searchQuery: query }),

  setInstances: (instances: EngineInstance[]) => set({ instances }),

  fetchInstances: async () => {
    set({ isLoading: true, error: null });
    try {
      const res = await fetch('/api/v1/engines/instances');
      if (res.ok) {
        const data = await res.json();
        if (data.instances && Array.isArray(data.instances)) {
          set({ instances: data.instances, isLoading: false });
          return;
        }
      }
      set({ isLoading: false });
    } catch {
      // Fallback preserves initial default instances when backend is offline or starting
      set({ isLoading: false });
    }
  },

  fetchEngineConfig: async (instanceId: string) => {
    try {
      const res = await fetch(`/api/v1/engines/${encodeURIComponent(instanceId)}/config`);
      if (res.ok) {
        const data = await res.json();
        return { port: data.port, extra_args: data.extra_args || [] };
      }
      return null;
    } catch {
      return null;
    }
  },

  saveEngineConfig: async (
    instanceId: string,
    config: { port: number; extraArgs: string[] }
  ): Promise<SaveEngineConfigResult> => {
    try {
      const res = await fetch(`/api/v1/engines/${encodeURIComponent(instanceId)}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          port: config.port,
          extra_args: config.extraArgs,
        }),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        return {
          success: false,
          message: data.detail || data.message || `Server error (HTTP ${res.status})`,
        };
      }

      const savedPort = data.port ?? config.port;
      const savedArgs = data.extra_args ?? config.extraArgs;

      set((state) => ({
        instances: state.instances.map((i) => {
          if (i.id !== instanceId) return i;
          let newEndpoint = i.endpoint;
          if (newEndpoint) {
            try {
              const url = new URL(newEndpoint);
              url.port = String(savedPort);
              newEndpoint = url.toString().replace(/\/$/, '');
            } catch {
              newEndpoint = `http://127.0.0.1:${savedPort}`;
            }
          } else {
            newEndpoint = `http://127.0.0.1:${savedPort}`;
          }
          return {
            ...i,
            port: savedPort,
            extra_args: savedArgs,
            endpoint: newEndpoint,
          };
        }),
      }));

      return {
        success: true,
        message: data.message || 'Configuration saved successfully.',
        requires_restart: Boolean(data.requires_restart),
      };
    } catch (err: any) {
      return {
        success: false,
        message: err.message || 'Network connection failed while saving configuration.',
      };
    }
  },

  startEngine: async (instanceId: string): Promise<StartEngineResult> => {
    const inst = get().instances.find((i) => i.id === instanceId);
    if (!inst) return { success: false, message: 'Instance not found' };

    // Only managed engines can be started via the app
    if (!inst.is_managed) {
      return { success: false, message: 'External engines cannot be started from the app. Start them manually.' };
    }

    try {
      // Route lifecycle controls by engine type
      const endpoint = inst.type === 'webui' ? '/api/v1/runtime/webui/start' : '/api/v1/runtime/start';
      const res = await fetch(endpoint, { method: 'POST' });
      if (res.ok) {
        const data = await res.json().catch(() => ({ success: false }));
        const isSuccess = data.success === true || (data.success !== false && data.status === 'started');
        if (isSuccess) {
          set((state) => ({
            instances: state.instances.map((i) =>
              i.id === instanceId ? { ...i, status: 'running', pid: data.pid } : i
            ),
          }));
          return { success: true, message: data.message, pid: data.pid };
        } else {
          // If uninstalled or env missing, reflect not_installed in status
          if (data.code === 'NOT_INSTALLED' || data.code === 'ENV_MISSING') {
            set((state) => ({
              instances: state.instances.map((i) =>
                i.id === instanceId ? { ...i, status: 'not_installed' } : i
              ),
            }));
          }
          return {
            success: false,
            code: data.code,
            message: data.message || 'Engine failed to start',
          };
        }
      }
      return { success: false, message: `Server error (HTTP ${res.status})` };
    } catch (e: any) {
      return { success: false, message: e.message || 'Network connection failed' };
    }
  },

  stopEngine: async (instanceId: string) => {
    const inst = get().instances.find((i) => i.id === instanceId);
    if (!inst) return false;

    // Only managed engines can be stopped via the app
    if (!inst.is_managed) {
      return false;
    }

    try {
      // Route lifecycle controls by engine type
      const endpoint = inst.type === 'webui' ? '/api/v1/runtime/webui/stop' : '/api/v1/runtime/stop';
      const res = await fetch(endpoint, { method: 'POST' });
      if (res.ok) {
        set((state) => ({
          instances: state.instances.map((i) =>
            i.id === instanceId ? { ...i, status: 'stopped' } : i
          ),
        }));
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },
}));
