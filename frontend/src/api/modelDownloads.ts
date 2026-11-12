import type { DownloadTask } from '../stores/useDownloadStore';

export interface DownloadTasksResponse { tasks: DownloadTask[] }

export async function listDownloadTasks(): Promise<DownloadTask[]> {
  const response = await fetch('/api/v1/models/hub/tasks');
  if (!response.ok) throw new Error(`Could not load downloads (HTTP ${response.status})`);
  const payload: DownloadTasksResponse = await response.json();
  if (!Array.isArray(payload.tasks)) throw new Error('Invalid download task response');
  return payload.tasks;
}
