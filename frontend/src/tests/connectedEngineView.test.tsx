// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ConnectedEngineView } from '../components/engine/ConnectedEngineView';
import { InstanceCard } from '../components/launcher/InstanceCard';
import { defaultBuiltinInstances, useEngineStore, type EngineInstance } from '../stores/useEngineStore';
import { useNavigationStore } from '../stores/useNavigationStore';

beforeEach(() => {
  useEngineStore.setState({ ...useEngineStore.getInitialState(), instances: defaultBuiltinInstances });
  useNavigationStore.setState(useNavigationStore.getInitialState());
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const noop = () => undefined;

it('starts WebUI through its own lifecycle endpoint even while ComfyUI is running', async () => {
  useEngineStore.setState({ instances: defaultBuiltinInstances.map((item) => item.type === 'comfyui' ? { ...item, status: 'running' } : item) });
  const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true, pid: 42 }) });
  vi.stubGlobal('fetch', fetcher);
  render(<ConnectedEngineView engineType="webui" onDeployEngine={noop} onOpenDirectory={noop} />);
  fireEvent.click(screen.getByRole('button', { name: 'Start SD WebUI Now' }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledExactlyOnceWith('/api/v1/runtime/webui/start', { method: 'POST' }));
  expect(useEngineStore.getState().instances.find((item) => item.type === 'comfyui')?.status).toBe('running');
  expect(screen.queryByRole('button', { name: 'Start SD WebUI Now' })).toBeNull();
});

it('preserves the selected external instance and its full HTTPS native URL', () => {
  const external: EngineInstance = { ...defaultBuiltinInstances[1], id: 'external-b', connection_id: 'external-b',
    name: 'Remote Comfy', is_managed: false, status: 'running', endpoint: 'https://example.invalid:9443/studio/?mode=canvas' };
  useEngineStore.setState({ instances: [...defaultBuiltinInstances, external] });
  render(<InstanceCard instance={external} />);
  fireEvent.click(screen.getByRole('button', { name: /Switch to View/ }));
  expect(useNavigationStore.getState().selectedEngineIds.comfyui).toBe(external.id);
  cleanup();
  const browser = vi.spyOn(window, 'open').mockReturnValue(null);
  render(<ConnectedEngineView engineType="comfyui" onDeployEngine={noop} onOpenDirectory={noop} />);
  expect(document.querySelector('iframe')?.getAttribute('src')).toBe(external.endpoint);
  fireEvent.click(screen.getByRole('button', { name: 'Browser' }));
  expect(browser).toHaveBeenCalledWith(external.endpoint, '_blank', 'noopener,noreferrer');
});

it('does not offer lifecycle control for an offline external connection', () => {
  useEngineStore.setState({ instances: [{ ...defaultBuiltinInstances[1], id: 'external', is_managed: false, status: 'stopped' }] });
  render(<ConnectedEngineView engineType="comfyui" onDeployEngine={noop} onOpenDirectory={noop} />);
  expect(screen.queryByRole('button', { name: /Start/ })).toBeNull();
  expect(screen.getByRole('status').textContent).toContain('outside Berry');
});

it('shows failed startup in the active engine view', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ success: false, message: 'Missing runtime environment' }) }));
  render(<ConnectedEngineView engineType="webui" onDeployEngine={noop} onOpenDirectory={noop} />);
  fireEvent.click(screen.getByRole('button', { name: 'Start SD WebUI Now' }));
  await waitFor(() => expect(screen.getByRole('alert').textContent).toBe('Missing runtime environment'));
});
