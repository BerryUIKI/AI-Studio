// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { CustomPlatformSettings } from '../components/cloud/CustomPlatformSettings';
import { CustomProviderRecord, CustomProviderSpec, customProviders, newCustomProvider } from '../api/customProviders';

vi.mock('../api/customProviders', async (original) => {
  const actual = await original<typeof import('../api/customProviders')>();
  return { ...actual, customProviders: { list: vi.fn(), save: vi.fn(), fixture: vi.fn(), prepare: vi.fn(), remove: vi.fn() } };
});

let records: CustomProviderRecord[];
const onChanged = vi.fn(async () => undefined);
beforeEach(() => {
  records = [];
  vi.mocked(customProviders.list).mockImplementation(async () => [...records]);
  vi.mocked(customProviders.save).mockImplementation(async (spec, approve) => {
    const record = { spec: { ...spec, revision: 'saved-revision' }, trusted_revision: approve ? 'saved-revision' : null, execution_trusted: approve };
    records = [record]; return record;
  });
  vi.mocked(customProviders.fixture).mockResolvedValue({ output: { type: 'image', value: { url: 'https://fixture.invalid/image.jpg' } }, broker_requests: 1, evidence_level: 'broker-fixture', live_inference: false });
  vi.mocked(customProviders.prepare).mockResolvedValue({ ready: true });
  vi.mocked(customProviders.remove).mockImplementation(async () => { records = []; return { success: true }; });
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

function fillPlatform() {
  fireEvent.change(screen.getByLabelText('Platform name'), { target: { value: 'Fixture platform' } });
  fireEvent.change(screen.getByLabelText('Request endpoint (HTTPS or localhost)'), { target: { value: 'https://fixture.invalid/images' } });
  fireEvent.change(screen.getByLabelText('Model IDs (one per line)'), { target: { value: 'model-one\nmodel-two' } });
}

it('saves REST mappings and runs only the explicit broker fixture after save', async () => {
  render(<CustomPlatformSettings onChanged={onChanged} />);
  fireEvent.click(screen.getByRole('button', { name: 'Add platform' }));
  fillPlatform();
  fireEvent.change(screen.getByLabelText('JSON request template'), { target: { value: '{"width":"{{width}}","model":"{{model}}"}' } });
  expect(screen.getByRole('button', { name: 'Run broker fixture' }).hasAttribute('disabled')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Save platform' }));
  await screen.findByText(/Platform saved/);
  expect(customProviders.save).toHaveBeenCalledWith(expect.objectContaining({ models: ['model-one', 'model-two'], body_template: { width: '{{width}}', model: '{{model}}' } }), false);
  expect(customProviders.fixture).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Run broker fixture' }));
  await screen.findByText(/Broker fixture passed: image output, 1 broker requests/);
  expect(customProviders.fixture).toHaveBeenCalledWith('custom-platform', {}, { data: [{ url: 'https://fixture.invalid/image.jpg' }] });
  fireEvent.change(screen.getByLabelText('Platform name'), { target: { value: 'Changed platform' } });
  expect(screen.getByRole('button', { name: 'Run broker fixture' }).hasAttribute('disabled')).toBe(true);
});

it('requires explicit approval after code/config edits and preserves drafts per language', async () => {
  render(<CustomPlatformSettings onChanged={onChanged} />);
  fireEvent.click(screen.getByRole('button', { name: 'Add platform' })); fillPlatform();
  fireEvent.change(screen.getByLabelText('Calling method'), { target: { value: 'javascript' } });
  fireEvent.change(screen.getByLabelText('Calling code'), { target: { value: "function execute(){return {type:'image',value:{url:'https://fixture.invalid/a.jpg'}}}" } });
  const js = (screen.getByLabelText('Calling code') as HTMLTextAreaElement).value;
  fireEvent.change(screen.getByLabelText('Calling method'), { target: { value: 'python' } });
  expect(screen.getByText(/Python is trusted code/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Calling method'), { target: { value: 'javascript' } });
  expect((screen.getByLabelText('Calling code') as HTMLTextAreaElement).value).toBe(js);
  const approval = screen.getByLabelText('I reviewed and approve this calling-code and dependency revision');
  fireEvent.click(approval);
  fireEvent.change(screen.getByLabelText('Maximum broker requests per execution'), { target: { value: '2' } });
  expect((approval as HTMLInputElement).checked).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: 'Save platform' }));
  await screen.findByText(/Platform saved/);
  expect(screen.getByRole('button', { name: 'Run broker fixture' }).hasAttribute('disabled')).toBe(true);
  fireEvent.click(approval);
  fireEvent.click(screen.getByRole('button', { name: 'Save platform' }));
  await waitFor(() => expect(customProviders.save).toHaveBeenLastCalledWith(expect.objectContaining({ mode: 'javascript', max_requests: 2 }), true));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run broker fixture' }).hasAttribute('disabled')).toBe(false));
});

it('separates SDK preparation and raw key opt-in from fixture execution and confirms removal', async () => {
  const spec: CustomProviderSpec = { ...newCustomProvider(), name: 'SDK fixture', models: ['model'], mode: 'python_sdk' };
  records = [{ spec, execution_trusted: true, trusted_revision: 'fixture-revision' }];
  render(<CustomPlatformSettings onChanged={onChanged} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Edit SDK fixture' }));
  expect((screen.getByLabelText(/Allow this SDK revision/) as HTMLInputElement).checked).toBe(false);
  expect(customProviders.prepare).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Prepare isolated SDK environment' }));
  await screen.findByText(/Isolated SDK environment prepared/);
  expect(customProviders.fixture).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Remove platform and key' }));
  expect(customProviders.remove).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Confirm removal' }));
  await waitFor(() => expect(customProviders.remove).toHaveBeenCalledWith(spec.id));
  expect(screen.queryByRole('button', { name: 'Edit SDK fixture' })).toBeNull();
});
