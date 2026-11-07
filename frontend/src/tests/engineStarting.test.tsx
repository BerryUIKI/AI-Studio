// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { InstanceCard } from '../components/launcher/InstanceCard';
import { defaultBuiltinInstances } from '../stores/useEngineStore';

afterEach(cleanup);
it('offers stop rather than duplicate startup while waiting for health', () => {
  const start = vi.fn();
  const stop = vi.fn();
  render(<InstanceCard instance={{ ...defaultBuiltinInstances[1], status: 'starting' }} onStart={start} onStop={stop} />);
  expect(screen.getByRole('status').textContent).toBe('Starting...');
  expect(screen.queryByRole('button', { name: 'Start' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Stop' }));
  expect(stop).toHaveBeenCalledWith('comfyui-managed');
  expect(start).not.toHaveBeenCalled();
});
