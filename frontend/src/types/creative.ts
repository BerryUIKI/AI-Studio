export type CreativeActionType = 'txt2img' | 'img2img' | 'inpaint' | 'upscale';

export interface GenerationProvenance {
  action: CreativeActionType;
  prompt: string;
  negative_prompt?: string;
  model: string;
  engine_id: string;
  seed: number;
  steps: number;
  cfg_scale: number;
  dimensions: string;
  created_at: string;
  source_asset_id?: string;
  mask_asset_id?: string;
  execution_time_ms?: number;
}

export interface CreativeActionRequest {
  action: CreativeActionType;
  prompt: string;
  negative_prompt?: string;
  model?: string;
  engine_id?: string;
  aspect_ratio?: string;
  width?: number;
  height?: number;
  steps?: number;
  cfg_scale?: number;
  seed?: number;
  denoise?: number;
  input_image_id?: string;
  mask_image_id?: string;
  upscale_factor?: number;
  upscaler_name?: string;
}

export interface CreativeActionResult {
  success: boolean;
  task_id: string;
  asset_id?: string;
  image_url?: string;
  width: number;
  height: number;
  provenance?: GenerationProvenance;
  is_cached?: boolean;
  error_message?: string;
}

export interface ImageCardData {
  assetId?: string;
  imageUrl: string;
  width: number;
  height: number;
  provenance?: GenerationProvenance;
  label?: string;
}
