export type CreativeActionType = 'txt2img' | 'img2img' | 'inpaint' | 'upscale' | 'txt2video' | 'img2video';

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
  fps?: number;
  num_frames?: number;
  duration_seconds?: number;
  motion_bucket_id?: number;
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
  fps?: number;
  num_frames?: number;
  motion_bucket_id?: number;
  duration_seconds?: number;
}

export interface CreativeActionResult {
  success: boolean;
  task_id: string;
  asset_id?: string;
  image_url?: string;
  video_url?: string;
  width: number;
  height: number;
  duration_seconds?: number;
  fps?: number;
  provenance?: GenerationProvenance;
  is_cached?: boolean;
  error_message?: string;
}

export interface ImageCardData {
  assetId?: string;
  imageUrl: string;
  videoUrl?: string;
  mediaType?: 'image' | 'video';
  width: number;
  height: number;
  provenance?: GenerationProvenance;
  label?: string;
}

export interface AgentActionStep {
  step_number: number;
  action: CreativeActionType;
  engine_id: string;
  model: string;
  parameters: Record<string, any>;
  description?: string;
}

export interface WorkflowNodeStage {
  stage_number: number;
  name: string;
  node_type: string;
  description: string;
}

export interface ReviewableWorkflowGraph {
  workflow_id: string;
  workflow_title: string;
  node_count: number;
  stages: WorkflowNodeStage[];
  required_nodes: string[];
  required_models: string[];
  missing_models: string[];
  is_valid: boolean;
  validation_issues: string[];
  recovery_guidance?: string;
}

export interface AgentProposal {
  id: string;
  intent: string;
  title: string;
  summary: string;
  target_engine: string;
  model: string;
  parameters: Record<string, any>;
  chain_steps: AgentActionStep[];
  workflow_graph?: ReviewableWorkflowGraph;
  estimated_calls: number;
  cost_disclaimer: string;
  explanation: string;
  requires_user_approval: boolean;
  approved: boolean;
}

export interface AgentChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  proposal?: AgentProposal;
  created_at: string;
}

