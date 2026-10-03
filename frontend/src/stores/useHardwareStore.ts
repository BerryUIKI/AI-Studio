import { create } from 'zustand';

export interface GpuProcess {
  pid: number;
  process_name: string;
  vram_used_mb: number;
}

export interface GpuStats {
  has_gpu: boolean;
  vendor: string;
  name: string;
  driver_version: string | null;
  temperature_c: number | null;
  utilization_pct: number | null;
  vram_total_mb: number;
  vram_used_mb: number;
  vram_free_mb: number;
  processes: GpuProcess[];
}

interface HardwareState {
  stats: GpuStats | null;
  isLoading: boolean;
  error: string | null;
  isPopoverOpen: boolean;

  setStats: (stats: GpuStats) => void;
  setIsPopoverOpen: (open: boolean) => void;
  fetchGpuStats: () => Promise<void>;
}

export const useHardwareStore = create<HardwareState>((set) => ({
  stats: null,
  isLoading: false,
  error: null,
  isPopoverOpen: false,

  setStats: (stats) => set({ stats }),
  setIsPopoverOpen: (open) => set({ isPopoverOpen: open }),

  fetchGpuStats: async () => {
    try {
      set({ isLoading: true, error: null });
      const res = await fetch('/api/v1/hardware/gpu-stats');
      if (!res.ok) {
        throw new Error(`Failed to fetch GPU stats: ${res.statusText}`);
      }
      const data: GpuStats = await res.json();
      set({ stats: data, isLoading: false });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown hardware telemetry error';
      set({ error: msg, isLoading: false });
    }
  },
}));
