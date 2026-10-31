// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { UpscaleModal } from '../components/canvas/UpscaleModal';
import { InpaintModal } from '../components/canvas/InpaintModal';
import { useCreativeStore } from '../stores/useCreativeStore';

beforeEach(() => useCreativeStore.setState({ ...useCreativeStore.getInitialState(),
  referenceImage: { assetId: 'fixture', imageUrl: '/fixture.png', width: 64, height: 48 },
  isGenerating: false, error: 'The selected engine is offline. Start it and retry.' }));
afterEach(() => { cleanup(); useCreativeStore.setState(useCreativeStore.getInitialState()); vi.restoreAllMocks(); });

it.each(['inpaint', 'upscale'])('shows the failure inside the active %s dialog and retains the source', (kind) => {
  useCreativeStore.setState({ inpaintModalOpen: kind === 'inpaint', upscaleModalOpen: kind === 'upscale' });
  render(kind === 'inpaint' ? <InpaintModal /> : <UpscaleModal />);
  const dialog = screen.getByRole('dialog');
  expect(within(dialog).getByRole('alert').textContent).toContain('engine is offline');
  fireEvent.click(within(dialog).getByRole('button', { name: 'Dismiss' }));
  expect(within(dialog).queryByRole('alert')).toBeNull();
  expect(useCreativeStore.getState().referenceImage?.assetId).toBe('fixture');
  expect(screen.getByRole('dialog')).toBeTruthy();
});

it('exposes actual task cancellation in the active upscale dialog', () => {
  const cancel = vi.fn().mockResolvedValue(undefined);
  useCreativeStore.setState({ upscaleModalOpen: true, isGenerating: true, activeTaskId: 'task-42',
    generationStage: 'Running', cancelGeneration: cancel, error: null });
  render(<UpscaleModal />);
  const dialog = screen.getByRole('dialog');
  fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
  expect(cancel).toHaveBeenCalledOnce();
  act(() => useCreativeStore.setState({ cancellationRequested: true, generationNotice: 'Remote work may continue.' }));
  expect(within(dialog).getByText('Remote work may continue.')).toBeTruthy();
  expect(within(dialog).getByRole('button', { name: 'Cancellation requested' }).hasAttribute('disabled')).toBe(true);
});
