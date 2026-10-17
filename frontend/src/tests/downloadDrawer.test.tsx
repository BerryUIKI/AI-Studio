// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { DownloadManagerDrawer } from '../components/hub/DownloadManagerDrawer';
import { useDownloadStore, type DownloadTask } from '../stores/useDownloadStore';
import { useSettingsStore } from '../stores/useSettingsStore';

export const downloadFixture: DownloadTask = {
  task_id: 'task', model_id: 'model', model_name: 'Model fixture', target_engine: 'comfyui',
  target_path: '/owned/model.safetensors', status: 'downloading', total_bytes: 100,
  downloaded_bytes: 25, progress_pct: 25, speed_bps: 10, eta_seconds: 3723,
};
beforeEach(() => {
  useSettingsStore.getState().setLanguage('en');
  useDownloadStore.setState({ isDrawerOpen: true, tasks: [downloadFixture] });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('reports removal failure and lets the user retry', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 409 })));
  render(<DownloadManagerDrawer />);
  fireEvent.click(screen.getByRole('button', { name: 'Cancel and remove incomplete download' }));
  expect(await screen.findByRole('alert')).toBeTruthy();
  expect(screen.getByText(/Could not remove the download/)).toBeTruthy();
  await waitFor(() => expect(screen.getByRole('button', { name: 'Cancel and remove incomplete download' }).hasAttribute('disabled')).toBe(false));
});

it('allows removing completed history while clearly preserving the model', async () => {
  useDownloadStore.setState({ tasks: [{ ...downloadFixture, status: 'completed' }] });
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}')));
  render(<DownloadManagerDrawer />);
  fireEvent.click(screen.getByRole('button', { name: 'Remove from list (keep installed model)' }));
  await waitFor(() => expect(screen.queryByText('Model fixture')).toBeNull());
});
