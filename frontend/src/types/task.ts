import { CreativeActionResult } from './creative';

export type TaskStatus = 'queued' | 'running' | 'cached' | 'succeeded' | 'failed' | 'cancel-requested' | 'cancelled' | 'interrupted' | 'outcome-unknown';

export interface GenerationTask {
  id: string;
  run_id: string;
  project_id?: string;
  node_type: string;
  status: TaskStatus;
  params: Record<string, unknown>;
  outputs: Partial<CreativeActionResult>;
  metadata: Record<string, unknown>;
  error?: string;
  created_at: string;
}
