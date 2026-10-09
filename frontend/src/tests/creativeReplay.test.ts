import { describe, expect, it } from 'vitest';
import { creativeRequestFromProvenance } from '../utils/creativeReplay';
import { GenerationProvenance } from '../types/creative';

const provenance: GenerationProvenance = {
  action: 'inpaint', prompt: 'replace background', model: 'effective-model', connection_id: 'studio',
  engine_id: 'comfyui', seed: 42, steps: 20, cfg_scale: 7, dimensions: '640x480', created_at: 'fixture',
  source_asset_id: 'source', mask_asset_id: 'mask',
  parameters: { action: 'inpaint', prompt: 'replace background', model: 'original-alias',
    denoise: 0.4, upscale_factor: 3, upscaler_name: 'saved-upscaler', seed: 42 },
};

describe('creative replay', () => {
  it('restores saved settings and source assets rather than the current dock values', () => {
    expect(creativeRequestFromProvenance(provenance)).toMatchObject({
      model: 'original-alias', input_image_id: 'source', mask_image_id: 'mask',
      width: 640, height: 480, denoise: 0.4, upscale_factor: 3, upscaler_name: 'saved-upscaler', seed: 42,
    });
  });
  it('changes only the seed when requesting a new variation', () => {
    const replay = creativeRequestFromProvenance(provenance);
    expect(creativeRequestFromProvenance(provenance, true)).toEqual({ ...replay, seed: -1 });
    expect(provenance.parameters?.seed).toBe(42);
  });
});
