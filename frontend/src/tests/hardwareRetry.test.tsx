// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { GpuStatusIndicator } from '../components/titlebar/GpuStatusIndicator';
import { GpuStats, useHardwareStore } from '../stores/useHardwareStore';

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it('keeps failed telemetry unavailable throughout a pending retry and clears it only with fresh stats', async () => {
  const stale: GpuStats = { has_gpu: true, vendor: 'NVIDIA', name: 'NVIDIA GeForce RTX 4060 Ti', driver_version: 'fixture',
    temperature_c: 40, utilization_pct: 0, vram_total_mb: 16384, vram_used_mb: 1024, vram_free_mb: 15360, processes: [] };
  let complete!: (value: Response) => void;
  const deferred = new Promise<Response>((resolve) => { complete = resolve; });
  vi.stubGlobal('fetch', vi.fn().mockRejectedValueOnce(new Error('Fixture offline')).mockReturnValueOnce(deferred));
  useHardwareStore.setState({ stats: stale, error: null, isLoading: false, isPopoverOpen: false });
  render(<GpuStatusIndicator />);
  await screen.findByText('GPU telemetry unavailable');
  let retry!: Promise<void>;
  act(() => { retry = useHardwareStore.getState().fetchGpuStats(); });
  expect(useHardwareStore.getState().isLoading).toBe(true);
  expect(screen.getByRole('status').textContent).toBe('GPU telemetry unavailable');
  expect(screen.queryByText('RTX 4060 Ti')).toBeNull();
  const fresh = { ...stale, temperature_c: 45, vram_used_mb: 2048 };
  await act(async () => { complete(new Response(JSON.stringify(fresh), { status: 200 })); await retry; });
  expect(useHardwareStore.getState().error).toBeNull();
  expect(useHardwareStore.getState().stats).toEqual(fresh);
  expect(screen.getByText('RTX 4060 Ti')).toBeTruthy();
});
