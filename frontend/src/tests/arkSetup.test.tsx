// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { CloudSettingsModal } from '../components/cloud/CloudSettingsModal';
import { CreationDock } from '../components/canvas/CreationDock';
import { useCreationSetupStore } from '../stores/useCreationSetupStore';
import { useCreativeStore } from '../stores/useCreativeStore';

const provider = {
  id: 'volcengine', name: 'Volcengine Ark', description: 'Fixture', is_configured: true,
  supported_models: ['doubao-seedream-4-0-250828'], capabilities: ['txt2img', 'img2img'],
  upload_disclosure: 'Fixture upload disclosure', website_url: 'https://fixture.invalid',
  key_test_supported: false,
};

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
beforeEach(() => {
  useCreationSetupStore.setState({ providers: [], models: [], loading: false, error: null });
  useCreativeStore.setState({ connectionId: '', model: '', referenceImage: null, isGenerating: false, error: null });
});

it('does not submit a paid inference behind Test Connection', async () => {
  const fetch = vi.fn(async (url: string) => ({ ok: true, json: async () => url.includes('custom-providers') ? [] : [provider] }));
  vi.stubGlobal('fetch', fetch);
  render(<CloudSettingsModal isOpen onClose={() => undefined} />);
  const test = await screen.findByRole('button', { name: 'Test Connection' });
  expect(test.hasAttribute('disabled')).toBe(true);
  fireEvent.click(test);
  expect(fetch.mock.calls.every(([url]) => url.endsWith('/providers') || url.endsWith('/custom-providers'))).toBe(true);
  expect(screen.getByText(/no verified free connection check/)).toBeTruthy();
});

it('refreshes canvas provider readiness after saving a fixture credential', async () => {
  let configured = false;
  vi.stubGlobal('fetch', vi.fn(async (_url: string, options?: RequestInit) => {
    if (options?.method === 'POST') configured = true;
    return { ok: true, json: async () => _url.includes('custom-providers') ? [] : options?.method === 'POST' ? {} : [{ ...provider, is_configured: configured }] };
  }));
  render(<CloudSettingsModal isOpen onClose={() => undefined} />);
  const input = await screen.findByLabelText('Volcengine Ark API key');
  fireEvent.change(input, { target: { value: 'fixture-secret' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save' }));
  await waitFor(() => expect(useCreationSetupStore.getState().providers[0]?.is_configured).toBe(true));
  expect((input as HTMLInputElement).value).toBe('');
});

it('selects Ark and exposes a variation control without a provider seed claim', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => ({ ok: true, json: async () => url.includes('providers') ? [provider] : [] })));
  render(<CreationDock />);
  await screen.findByRole('option', { name: 'Volcengine Ark' });
  fireEvent.change(screen.getByLabelText('Create with'), { target: { value: 'volcengine' } });
  expect(useCreativeStore.getState().model).toBe(provider.supported_models[0]);
  expect(screen.getByRole('button', { name: 'Generate Image' }).hasAttribute('disabled')).toBe(false);
  expect(screen.getByRole('button', { name: 'New Variation' })).toBeTruthy();
  expect(screen.queryByText('Advanced')).toBeNull();
});
