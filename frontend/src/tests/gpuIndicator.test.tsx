// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { GpuStatusIndicator } from '../components/titlebar/GpuStatusIndicator';
import { GpuStats, useHardwareStore } from '../stores/useHardwareStore';

const gpu: GpuStats = { has_gpu: true, vendor: 'NVIDIA', name: 'NVIDIA GeForce RTX 4060 Ti',
  driver_version: 'fixture', temperature_c: 40, utilization_pct: 0,
  vram_total_mb: 16384, vram_used_mb: 1024, vram_free_mb: 15360, processes: [] };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('does not assert absent hardware during discovery or failed polling', () => {
  const probe = vi.spyOn(useHardwareStore.getState(), 'fetchGpuStats').mockResolvedValue();
  useHardwareStore.setState({ stats: null, error: null, isPopoverOpen: false });
  render(<GpuStatusIndicator />);
  expect(screen.getByRole('status').textContent).toBe('Checking GPU…');
  expect(screen.queryByText('Cloud Mode')).toBeNull();
  act(() => useHardwareStore.setState({ stats: gpu }));
  expect(screen.getByText('RTX 4060 Ti')).toBeTruthy();
  act(() => useHardwareStore.setState({ error: 'fixture polling failure' }));
  expect(screen.getByRole('status').textContent).toBe('GPU telemetry unavailable');
  expect(screen.queryByText('RTX 4060 Ti')).toBeNull();
  act(() => useHardwareStore.setState({ error: null, stats: { ...gpu, has_gpu: false } }));
  expect(screen.getByText('Cloud Mode')).toBeTruthy();
  expect(probe).toHaveBeenCalledOnce();
});
