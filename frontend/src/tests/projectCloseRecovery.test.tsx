// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from '../App';
import { useProjectStore } from '../stores/useProjectStore';
import { useEngineStore } from '../stores/useEngineStore';
import { useSettingsStore } from '../stores/useSettingsStore';
import type { Project } from '../types/project';
import type { TitlebarProps } from '../components/titlebar/Titlebar';

vi.mock('../components/titlebar/Titlebar', () => ({ Titlebar: (props: TitlebarProps) => <button onClick={props.onCloseRequested}>Close Berry</button> }));
vi.mock('../components/canvas/FlowCanvas', () => ({ FlowCanvas: () => null }));
const project: Project = { id: 'close-project', name: 'Keep my edits', version: 1,
  created_at: '2026-10-19T00:00:00Z', updated_at: '2026-10-19T00:00:00Z',
  canvas: { version: 1, nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } } };
afterEach(() => { cleanup(); useProjectStore.setState(useProjectStore.getInitialState()); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it('keeps the app open after a save failure and closes only after an explicit successful retry', async () => {
  let fail = true;
  useProjectStore.setState({ ...useProjectStore.getInitialState(), currentProject: project, isDirty: true,
    initProject: vi.fn().mockResolvedValue(project) });
  useEngineStore.setState({ instances: [] });
  useSettingsStore.setState({ defaultLandingView: 'canvas', exitPolicy: 'prompt' });
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'PUT') return { ok: !fail, status: fail ? 500 : 200, json: async () => project };
    return { ok: true, json: async () => url.includes('/instances') ? { instances: [] }
      : url.includes('/tasks/active') ? { active_tasks_count: 0 }
      : url.includes('/status') ? { running: false, installed: false, online: false } : [] };
  }));
  const close = vi.spyOn(window, 'close').mockImplementation(() => undefined);
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: 'Close Berry' }));
  await waitFor(() => expect(screen.getByText('Save failed with HTTP 500')).toBeTruthy());
  expect(close).not.toHaveBeenCalled();
  expect(useProjectStore.getState().isDirty).toBe(true);
  fail = false;
  fireEvent.click(screen.getByRole('button', { name: 'Close Berry' }));
  await waitFor(() => expect(close).toHaveBeenCalledOnce());
  expect(useProjectStore.getState().isDirty).toBe(false);
});
