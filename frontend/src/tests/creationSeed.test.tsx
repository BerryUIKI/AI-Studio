// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CreationDock } from '../components/canvas/CreationDock';
import { useCreativeStore } from '../stores/useCreativeStore';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('preserves seed zero instead of replacing it with random generation', () => {
  useCreativeStore.setState({ ...useCreativeStore.getInitialState(), connectionId: 'comfyui-managed' });
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
  render(<CreationDock />);
  fireEvent.click(screen.getByRole('button', { name: 'Advanced' }));
  const seed = screen.getByLabelText('Seed (-1 for Random):');
  fireEvent.change(seed, { target: { value: '0' } });
  expect(useCreativeStore.getState().seed).toBe(0);
  fireEvent.change(seed, { target: { value: '' } });
  expect(useCreativeStore.getState().seed).toBe(-1);
});
