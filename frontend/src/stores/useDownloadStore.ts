import { create } from 'zustand';

export type DownloadTaskStatus = 'pending' | 'downloading' | 'paused' | 'completed' | 'failed' | 'cancelled';

export interface DownloadTask {
  task_id: string;
  model_id: string;
  model_name: string;
  target_engine: string;
  target_path: string;
  status: DownloadTaskStatus;
  total_bytes: number;
  downloaded_bytes: number;
  progress_pct: number;
  speed_bps: number;
  eta_seconds?: number | null;
  error_message?: string | null;
}

interface DownloadState {
  tasks: DownloadTask[];
  isDrawerOpen: boolean;
  isPolling: boolean;
  pollTimer: number | null;

  setDrawerOpen: (open: boolean) => void;
  toggleDrawer: () => void;
  fetchTasks: () => Promise<void>;
  startDownload: (modelId: string, targetEngine?: string, mirrorPreset?: string) => Promise<DownloadTask | null>;
  pauseTask: (taskId: string) => Promise<boolean>;
  resumeTask: (taskId: string) => Promise<boolean>;
  cancelTask: (taskId: string) => Promise<boolean>;
  startPolling: () => void;
  stopPolling: () => void;

  // Computed metrics
  getActiveCount: () => number;
  getTotalSpeedBps: () => number;
}

export const useDownloadStore = create<DownloadState>((set, get) => ({
  tasks: [],
  isDrawerOpen: false,
  isPolling: false,
  pollTimer: null,

  setDrawerOpen: (open) => set({ isDrawerOpen: open }),
  toggleDrawer: () => set((state) => ({ isDrawerOpen: !state.isDrawerOpen })),

  fetchTasks: async () => {
    try {
      const res = await fetch('/api/v1/models/hub/tasks');
      if (res.ok) {
        const data = await res.json();
        const tasks: DownloadTask[] = data.tasks || [];
        set({ tasks });

        // Auto manage polling based on active tasks
        const hasActive = tasks.some((t) => t.status === 'downloading' || t.status === 'pending');
        if (!hasActive && get().isPolling) {
          get().stopPolling();
        }
      }
    } catch {
      // Ignore network errors in polling
    }
  },

  startDownload: async (modelId: string, targetEngine = 'comfyui', mirrorPreset?: string) => {
    try {
      const res = await fetch('/api/v1/models/hub/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_id: modelId,
          target_engine: targetEngine,
          mirror_preset: mirrorPreset,
        }),
      });

      if (!res.ok) {
        throw new Error(`Failed to start download: ${res.statusText}`);
      }

      const task: DownloadTask = await res.json();
      set((state) => {
        const filtered = state.tasks.filter((t) => t.task_id !== task.task_id);
        return { tasks: [task, ...filtered] };
      });

      // Start polling
      get().startPolling();
      return task;
    } catch (err) {
      console.error('Download error:', err);
      return null;
    }
  },

  pauseTask: async (taskId: string) => {
    try {
      const res = await fetch(`/api/v1/models/hub/tasks/${taskId}/pause`, { method: 'POST' });
      if (res.ok) {
        set((state) => ({
          tasks: state.tasks.map((t) => (t.task_id === taskId ? { ...t, status: 'paused', speed_bps: 0 } : t)),
        }));
        return true;
      }
    } catch {
      // ignore
    }
    return false;
  },

  resumeTask: async (taskId: string) => {
    try {
      const res = await fetch(`/api/v1/models/hub/tasks/${taskId}/resume`, { method: 'POST' });
      if (res.ok) {
        set((state) => ({
          tasks: state.tasks.map((t) => (t.task_id === taskId ? { ...t, status: 'downloading' } : t)),
        }));
        get().startPolling();
        return true;
      }
    } catch {
      // ignore
    }
    return false;
  },

  cancelTask: async (taskId: string) => {
    try {
      const res = await fetch(`/api/v1/models/hub/tasks/${taskId}`, { method: 'DELETE' });
      if (res.ok) {
        set((state) => ({
          tasks: state.tasks.map((t) => (t.task_id === taskId ? { ...t, status: 'cancelled', speed_bps: 0 } : t)),
        }));
        return true;
      }
    } catch {
      // ignore
    }
    return false;
  },

  startPolling: () => {
    if (get().isPolling) return;
    const timer = setInterval(() => {
      get().fetchTasks();
    }, 2000) as unknown as number;
    set({ isPolling: true, pollTimer: timer });
  },

  stopPolling: () => {
    const { pollTimer } = get();
    if (pollTimer !== null) {
      clearInterval(pollTimer);
    }
    set({ isPolling: false, pollTimer: null });
  },

  getActiveCount: () => {
    return get().tasks.filter((t) => t.status === 'downloading' || t.status === 'pending').length;
  },

  getTotalSpeedBps: () => {
    return get().tasks
      .filter((t) => t.status === 'downloading')
      .reduce((acc, t) => acc + (t.speed_bps || 0), 0);
  },
}));
