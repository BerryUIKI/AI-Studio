import { afterEach, expect, it, vi } from 'vitest';
import { listDownloadTasks } from '../api/modelDownloads';
import { errorMessage } from '../utils/errors';

afterEach(() => vi.unstubAllGlobals());

it('reads the backend task envelope instead of waiting for an array response', async () => {
  const task = { task_id: 'download-1', status: 'completed' };
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ tasks: [task] }) }));
  expect(await listDownloadTasks()).toEqual([task]);
});

it('fails visibly on an invalid envelope or HTTP failure', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
  await expect(listDownloadTasks()).rejects.toThrow('Invalid download task response');
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }));
  await expect(listDownloadTasks()).rejects.toThrow('HTTP 503');
});

it('formats unknown error values without assuming they expose message', () => {
  expect(errorMessage(new Error('Failure'), 'Fallback')).toBe('Failure');
  expect(errorMessage({ message: 'Legacy failure' }, 'Fallback')).toBe('Legacy failure');
  expect(errorMessage(null, 'Fallback')).toBe('Fallback');
  expect(errorMessage({ message: 7 }, 'Fallback')).toBe('Fallback');
});
