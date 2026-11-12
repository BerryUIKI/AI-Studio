// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ProviderRegistry } from '../components/cloud/ProviderRegistry';
import { customProviders } from '../api/customProviders';

vi.mock('../api/customProviders', async (original) => {
  const actual = await original<typeof import('../api/customProviders')>();
  return { ...actual, customProviders: { list: vi.fn(), save: vi.fn(), remove: vi.fn() } };
});

const llmConfig = { provider: 'llama_server', model: 'qwen2.5', base_url: 'http://127.0.0.1:8080/v1', api_key: 'sk-...abcd', enabled: true };

beforeEach(() => {
  vi.mocked(customProviders.list).mockResolvedValue([]);
  vi.mocked(customProviders.remove).mockResolvedValue({ success: true });
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/api/v1/agent/llm/config')) return new Response(JSON.stringify(llmConfig), { status: 200 });
    if (url.includes('/api/v1/cloud/providers')) {
      return new Response(JSON.stringify([{
        id: 'fal', name: 'fal.ai', description: 'Image host', is_configured: false, supported_models: [],
        capabilities: ['txt2img'], upload_disclosure: '', website_url: 'https://fal.ai',
      }]), { status: 200 });
    }
    return new Response('[]', { status: 200 });
  }));
});
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); });

it('splits language and image providers into separate access types', async () => {
  render(<ProviderRegistry />);
  expect(await screen.findByText('OpenAI')).toBeTruthy();
  expect(screen.queryByText('fal.ai')).toBeNull();

  fireEvent.click(screen.getByText('Image models'));
  expect(await screen.findByText('fal.ai')).toBeTruthy();
  expect(screen.queryByText('OpenAI')).toBeNull();
});

it('marks only the provider that the saved configuration names', async () => {
  render(<ProviderRegistry />);
  await screen.findByText('llama.cpp');
  const configured = screen.getAllByLabelText('Configured');
  expect(configured).toHaveLength(1);
});

it('opens a custom endpoint form when the directory has no match', async () => {
  render(<ProviderRegistry />);
  await screen.findByText('OpenAI');
  // Language models save through the agent config; custom REST endpoints belong to image access.
  fireEvent.click(screen.getByText('Image models'));
  fireEvent.click(await screen.findByText('Add custom'));
  const url = await screen.findByLabelText('API base URL');
  fireEvent.change(url, { target: { value: 'https://relay.example.com/v1' } });
  fireEvent.change(screen.getByLabelText('Display name'), { target: { value: 'Company relay' } });
  fireEvent.change(screen.getByLabelText('Model ID'), { target: { value: 'gpt-4o' } });
  fireEvent.click(screen.getByText('Save'));

  await waitFor(() => expect(customProviders.save).toHaveBeenCalledTimes(1));
  const [spec] = vi.mocked(customProviders.save).mock.calls[0];
  expect(spec.endpoint).toBe('https://relay.example.com/v1');
  expect(spec.name).toBe('Company relay');
  expect(spec.models).toEqual(['gpt-4o']);
});
