// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ProgressBar } from '../components/ui/ProgressBar';
import { DeploymentDrawer } from '../components/launcher/DeploymentDrawer';

beforeEach(() => Object.defineProperty(Element.prototype, 'scrollIntoView', { value: vi.fn(), configurable: true }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('leaves indeterminate work unquantified and clamps observed values', () => {
  const view = render(<ProgressBar label="Work" />);
  expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBeNull();
  view.rerender(<ProgressBar label="Work" value={125} />);
  expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('100');
});

it('does not turn an installation phase into an invented percentage', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ phase: 'downloading' }) }));
  render(<DeploymentDrawer isOpen engineType="comfyui" onClose={vi.fn()} />);
  await waitFor(() => expect(screen.getByRole('progressbar', { name: 'Engine installation' }).getAttribute('aria-valuenow')).toBeNull());
  expect(screen.queryByText(/60%|10%/)).toBeNull();
  expect(screen.getAllByText(/Waiting for observed progress/).length).toBeGreaterThan(0);
});
