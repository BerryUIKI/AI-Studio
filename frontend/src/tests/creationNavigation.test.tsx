// @vitest-environment jsdom
import { useState } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { CreationDock } from '../components/canvas/CreationDock';
import { EnvironmentManagerModal } from '../components/manager/EnvironmentManagerModal';
import { useCreativeStore } from '../stores/useCreativeStore';
import { useEngineStore } from '../stores/useEngineStore';
import { useCreationSetupStore } from '../stores/useCreationSetupStore';

beforeEach(() => {
  useCreativeStore.setState(useCreativeStore.getInitialState());
  useCreationSetupStore.setState({ models: [], providers: [], loading: false, error: null });
  vi.stubGlobal('fetch', vi.fn(async (url: string) => ({ ok: true, json: async () => url.endsWith('/manager/status') ? null : [] })));
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it('opens the local model inventory repeatedly without relying on hash changes', async () => {
  function Workspace() {
    const [open, setOpen] = useState(false);
    return <><CreationDock onOpenModels={() => setOpen(true)} />
      <EnvironmentManagerModal isOpen={open} initialTab="models" onClose={() => setOpen(false)} /></>;
  }
  render(<Workspace />);
  for (let index = 0; index < 2; index++) {
    fireEvent.click(screen.getByRole('button', { name: 'Models ↗' }));
    expect(await screen.findByPlaceholderText(/directory|path/i)).toBeTruthy();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
  }
  expect(window.location.hash).toBe('');
});

it('selects a registered external engine and its validated local model for creation', async () => {
  const model = { id: 'model', name: 'Model', file_path: 'D:/models/sd15.safetensors', category: 'checkpoint', is_ready: true, engine_compatibility: ['comfyui'] };
  useEngineStore.setState({ instances: [{ id: 'external-review', connection_id: 'external-review', type: 'comfyui',
    name: 'External Studio', status: 'running', is_builtin: false, is_managed: false, capabilities: ['txt2img'] }] });
  vi.stubGlobal('fetch', vi.fn(async (url: string) => ({ ok: true, json: async () => url.endsWith('/models') ? [model] : [] })));
  render(<CreationDock />);
  await waitFor(() => expect(useCreationSetupStore.getState().models).toHaveLength(1));
  fireEvent.change(screen.getByLabelText('Create with'), { target: { value: 'external-review' } });
  expect(useCreativeStore.getState().connectionId).toBe('external-review');
  expect(useCreativeStore.getState().model).toBe('sd15.safetensors');
  expect(screen.getByRole('button', { name: 'Generate Image' }).hasAttribute('disabled')).toBe(false);
});
