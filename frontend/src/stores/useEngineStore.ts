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
}

interface EngineState {
  instances: EngineInstance[];
  isLoading: boolean;
  error: string | null;
  searchQuery: string;

  setSearchQuery: (query: string) => void;
  setInstances: (instances: EngineInstance[]) => void;
  fetchInstances: () => Promise<void>;
  startEngine: (instanceId: string) => Promise<boolean>;
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
    capabilities: ['txt2img', 'img2img', 'workflows'],
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
    capabilities: ['txt2img', 'img2img', 'inpaint'],
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

  startEngine: async (instanceId: string) => {
    const inst = get().instances.find((i) => i.id === instanceId);
    if (!inst) return false;

    try {
      const endpoint = inst.type === 'webui' ? '/api/v1/runtime/webui/start' : '/api/v1/runtime/start';
      const res = await fetch(endpoint, { method: 'POST' });
      if (res.ok) {
        set((state) => ({
          instances: state.instances.map((i) =>
            i.id === instanceId ? { ...i, status: 'running' } : i
          ),
        }));
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  stopEngine: async (instanceId: string) => {
    const inst = get().instances.find((i) => i.id === instanceId);
    if (!inst) return false;

    try {
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
