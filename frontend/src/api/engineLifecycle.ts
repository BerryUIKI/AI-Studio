import type { EngineInstance } from '../stores/useEngineStore';

export interface EngineRemovalResult {
  retained_path: string | null;
  warning: string | null;
}

async function request(url: string, method: 'POST' | 'DELETE'): Promise<Record<string, unknown>> {
  const response = await fetch(url, { method });
  const data: unknown = await response.json();
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Invalid engine response');
  const record = data as Record<string, unknown>;
  if (!response.ok || record.success === false) {
    throw new Error(typeof record.detail === 'string' ? record.detail
      : typeof record.message === 'string' ? record.message : `Engine action failed (HTTP ${response.status})`);
  }
  return record;
}

export async function removeEngine(instance: EngineInstance): Promise<EngineRemovalResult> {
  if (instance.is_builtin) throw new Error('Built-in workspaces cannot be removed');
  if (instance.is_managed && instance.type !== 'comfyui' && instance.type !== 'webui') {
    throw new Error('This managed engine does not support uninstall');
  }
  const data = await request(instance.is_managed
    ? `/api/v1/runtime/${instance.type}/uninstall`
    : `/api/v1/engines/unbind/${encodeURIComponent(instance.id)}`, instance.is_managed ? 'POST' : 'DELETE');
  return {
    retained_path: typeof data.retained_path === 'string' ? data.retained_path : null,
    warning: typeof data.warning === 'string' ? data.warning : null,
  };
}

export async function openEngineDirectory(instanceId: string): Promise<string> {
  const data = await request(`/api/v1/engines/${encodeURIComponent(instanceId)}/open-directory`, 'POST');
  if (typeof data.path !== 'string') throw new Error('The engine directory was not returned');
  return data.path;
}
