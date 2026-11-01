import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useHardwareStore, GpuStats } from '../stores/useHardwareStore';

describe('useHardwareStore', () => {
  beforeEach(() => {
    useHardwareStore.setState({
      stats: null,
      isLoading: false,
      error: null,
      isPopoverOpen: false,
    });
    vi.restoreAllMocks();
  });

  it('initializes with null stats and closed popover', () => {
    const state = useHardwareStore.getState();
    expect(state.stats).toBeNull();
    expect(state.isLoading).toBe(false);
    expect(state.isPopoverOpen).toBe(false);
  });

  it('updates popover open state', () => {
    const store = useHardwareStore.getState();
    store.setIsPopoverOpen(true);
    expect(useHardwareStore.getState().isPopoverOpen).toBe(true);
    store.setIsPopoverOpen(false);
    expect(useHardwareStore.getState().isPopoverOpen).toBe(false);
  });

  it('fetches GPU stats successfully when GPU is present', async () => {
    const mockStats: GpuStats = {
      has_gpu: true,
      vendor: 'nvidia',
      name: 'NVIDIA GeForce RTX 4090',
      driver_version: '555.42.02',
      temperature_c: 54,
      utilization_pct: 35,
      vram_total_mb: 24576,
      vram_used_mb: 6144,
      vram_free_mb: 18432,
      processes: [
        { pid: 101, process_name: 'ComfyUI', vram_used_mb: 5800 },
        { pid: 102, process_name: 'Berry Backend', vram_used_mb: 120 },
      ],
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockStats,
    });

    const store = useHardwareStore.getState();
    await store.fetchGpuStats();

    const state = useHardwareStore.getState();
    expect(state.stats).not.toBeNull();
    expect(state.stats?.has_gpu).toBe(true);
    expect(state.stats?.name).toBe('NVIDIA GeForce RTX 4090');
    expect(state.stats?.vram_used_mb).toBe(6144);
    expect(state.stats?.processes.length).toBe(2);
    expect(state.error).toBeNull();
  });

  it('handles fallback when no GPU is detected (cloud mode)', async () => {
    const mockFallback: GpuStats = {
      has_gpu: false,
      vendor: 'none',
      name: 'No Dedicated GPU',
      driver_version: null,
      temperature_c: null,
      utilization_pct: null,
      vram_total_mb: 0,
      vram_used_mb: 0,
      vram_free_mb: 0,
      processes: [],
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockFallback,
    });

    const store = useHardwareStore.getState();
    await store.fetchGpuStats();

    const state = useHardwareStore.getState();
    expect(state.stats?.has_gpu).toBe(false);
    expect(state.stats?.vendor).toBe('none');
    expect(state.error).toBeNull();
  });

  it('handles fetch error gracefully without throwing', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      statusText: 'Internal Server Error',
    });

    const store = useHardwareStore.getState();
    await store.fetchGpuStats();

    const state = useHardwareStore.getState();
    expect(state.error).toContain('Failed to fetch GPU stats');
    expect(state.isLoading).toBe(false);
  });
});
