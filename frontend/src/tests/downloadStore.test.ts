import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useDownloadStore } from '../stores/useDownloadStore';

describe('useDownloadStore (MH-M5)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useDownloadStore.setState({
      tasks: [],
      isDrawerOpen: false,
      isPolling: false,
      pollTimer: null,
    });
  });

  it('manages drawer open and toggle states correctly', () => {
    const { isDrawerOpen, setDrawerOpen, toggleDrawer } = useDownloadStore.getState();
    expect(isDrawerOpen).toBe(false);

    setDrawerOpen(true);
    expect(useDownloadStore.getState().isDrawerOpen).toBe(true);

    toggleDrawer();
    expect(useDownloadStore.getState().isDrawerOpen).toBe(false);
  });

  it('calculates active download count and aggregated speed accurately', () => {
    useDownloadStore.setState({
      tasks: [
        {
          task_id: 'dl_1',
          model_id: 'flux-1-schnell-fp8',
          model_name: 'FLUX.1 [schnell] FP8',
          target_engine: 'comfyui',
          target_path: '/models/checkpoints/flux.safetensors',
          status: 'downloading',
          total_bytes: 12000000000,
          downloaded_bytes: 6000000000,
          progress_pct: 50.0,
          speed_bps: 20971520, // 20 MB/s
          eta_seconds: 300,
        },
        {
          task_id: 'dl_2',
          model_id: 'sdxl-turbo',
          model_name: 'SDXL Turbo 1.0',
          target_engine: 'comfyui',
          target_path: '/models/checkpoints/sdxl.safetensors',
          status: 'downloading',
          total_bytes: 6900000000,
          downloaded_bytes: 3450000000,
          progress_pct: 50.0,
          speed_bps: 10485760, // 10 MB/s
          eta_seconds: 300,
        },
        {
          task_id: 'dl_3',
          model_id: 'upscaler-4x-ultrasharp',
          model_name: '4x-UltraSharp Upscaler',
          target_engine: 'comfyui',
          target_path: '/models/upscale_models/4x.pth',
          status: 'completed',
          total_bytes: 67000000,
          downloaded_bytes: 67000000,
          progress_pct: 100.0,
          speed_bps: 0,
          eta_seconds: 0,
        },
      ],
    });

    const activeCount = useDownloadStore.getState().getActiveCount();
    const totalSpeed = useDownloadStore.getState().getTotalSpeedBps();

    expect(activeCount).toBe(2);
    expect(totalSpeed).toBe(31457280); // 30 MB/s
  });

  it('handles startDownload and updates task list', async () => {
    const mockTask = {
      task_id: 'dl_new_1',
      model_id: 'lora-detail-tweaker',
      model_name: 'Detail Tweaker LoRA',
      target_engine: 'comfyui',
      target_path: '/models/loras/detail.safetensors',
      status: 'pending' as const,
      total_bytes: 150000000,
      downloaded_bytes: 0,
      progress_pct: 0.0,
      speed_bps: 0,
      eta_seconds: null,
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockTask,
    } as unknown as Response);

    const result = await useDownloadStore.getState().startDownload('lora-detail-tweaker');
    expect(result).not.toBeNull();
    expect(result?.task_id).toBe('dl_new_1');
    expect(useDownloadStore.getState().tasks.length).toBe(1);
    expect(useDownloadStore.getState().isPolling).toBe(true);

    useDownloadStore.getState().stopPolling();
  });
});
