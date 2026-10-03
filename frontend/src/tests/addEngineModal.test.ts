import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('Engine Auto-Detection and Binding Client', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('scans candidate directories through detect API', async () => {
    const mockDetected = [
      {
        engine_type: 'comfyui',
        path: 'D:\\ComfyUI_windows_portable\\ComfyUI',
        has_python_env: true,
        recommended_name: 'ComfyUI Portable',
      },
    ];

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ detected: mockDetected }),
    });

    const res = await fetch('/api/v1/engines/detect');
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.detected.length).toBe(1);
    expect(data.detected[0].engine_type).toBe('comfyui');
  });

  it('submits external engine bind request', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 'ext_comfyui_123',
        name: 'My ComfyUI',
        ownership: 'external',
      }),
    });

    const res = await fetch('/api/v1/engines/bind', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        engine_type: 'comfyui',
        name: 'My ComfyUI',
        path: 'D:\\ComfyUI',
        port: 8188,
      }),
    });

    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.id).toBe('ext_comfyui_123');
    expect(data.ownership).toBe('external');
  });

  it('handles mirrors configuration API', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        active_preset: 'china_mainland',
        presets: [
          { id: 'direct', name: 'Direct' },
          { id: 'china_mainland', name: 'China Mainland' },
        ],
      }),
    });

    const res = await fetch('/api/v1/installer/mirrors');
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.active_preset).toBe('china_mainland');
    expect(data.presets.length).toBe(2);
  });
});
