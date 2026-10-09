import { CreativeActionRequest, GenerationProvenance } from '../types/creative';

/** Restore the original input assets and settings, including action-specific parameters. */
export function creativeRequestFromProvenance(
  provenance: GenerationProvenance,
  variation = false,
): CreativeActionRequest {
  const [width, height] = provenance.dimensions.split('x').map(Number);
  return {
    action: provenance.action,
    prompt: provenance.prompt,
    negative_prompt: provenance.negative_prompt,
    model: provenance.model,
    connection_id: provenance.connection_id,
    engine_id: provenance.engine_id,
    steps: provenance.steps,
    cfg_scale: provenance.cfg_scale,
    aspect_ratio: undefined,
    width: width || undefined,
    height: height || undefined,
    input_image_id: provenance.source_asset_id,
    mask_image_id: provenance.mask_asset_id,
    fps: provenance.fps,
    num_frames: provenance.num_frames,
    duration_seconds: provenance.duration_seconds,
    motion_bucket_id: provenance.motion_bucket_id,
    ...provenance.parameters,
    seed: variation ? -1 : provenance.seed,
  };
}
