import { afterEach, describe, expect, it, vi } from 'vitest';
import { openEngineDirectory, removeEngine } from './engineLifecycle';
import type { EngineInstance } from '../stores/useEngineStore';

const managed: EngineInstance = {
  id: 'comfyui-managed', name: 'ComfyUI', type: 'comfyui', is_managed: true,
  is_builtin: false, status: 'stopped', capabilities: [],
};

afterEach(() => vi.unstubAllGlobals());

describe('engine action contracts', () => {
  it('managed uninstall uses the uninstall endpoint and returns retained data', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, retained_path: 'fixture/backup' })));
    vi.stubGlobal('fetch', fetch);
    expect((await removeEngine(managed)).retained_path).toBe('fixture/backup');
    expect(fetch).toHaveBeenCalledWith('/api/v1/runtime/comfyui/uninstall', { method: 'POST' });
  });

  it('external removal deletes only the connection', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true })));
    vi.stubGlobal('fetch', fetch);
    await removeEngine({ ...managed, id: 'external/fixture', is_managed: false });
    expect(fetch).toHaveBeenCalledWith('/api/v1/engines/unbind/external%2Ffixture', { method: 'DELETE' });
  });

  it('propagates refusal instead of reporting successful removal', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Stop the managed engine' }), { status: 409 })));
    await expect(removeEngine(managed)).rejects.toThrow('Stop the managed engine');
  });

  it('does not dispatch removal for built-in workspaces', async () => {
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    await expect(removeEngine({ ...managed, is_builtin: true })).rejects.toThrow('Built-in');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('opens the registered directory and preserves missing-directory errors', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ path: 'fixture/comfyui' })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'No local directory recorded' }), { status: 404 }));
    vi.stubGlobal('fetch', fetch);
    expect(await openEngineDirectory(managed.id)).toBe('fixture/comfyui');
    await expect(openEngineDirectory('remote')).rejects.toThrow('No local directory');
  });
});
