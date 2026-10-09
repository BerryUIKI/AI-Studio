import { mediaCardFields } from '../../utils/media';
import { useCallback, useEffect, useState } from 'react';
import { useProjectStore } from '../../stores/useProjectStore';
import { useCreativeStore } from '../../stores/useCreativeStore';
import { useCanvasStore } from '../../stores/useCanvasStore';
import { GenerationTask } from '../../types/task';

export function TaskHistory() {
  const projectId = useProjectStore((state) => state.currentProject?.id);
  const generating = useCreativeStore((state) => state.isGenerating);
  const [open, setOpen] = useState(false);
  const [tasks, setTasks] = useState<GenerationTask[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    if (!projectId) return;
    try {
      const response = await fetch(`/api/v1/tasks/history?project_id=${encodeURIComponent(projectId)}`, { signal });
      if (!response.ok) throw new Error(`Could not load history (${response.status})`);
      const history: GenerationTask[] = await response.json();
      if (signal?.aborted || useProjectStore.getState().currentProject?.id !== projectId) return;
      setTasks(history);
      setError(null);
    } catch (cause) {
      if (!signal?.aborted) setError(cause instanceof Error ? cause.message : 'Could not load history');
    }
  }, [projectId]);

  useEffect(() => {
    setTasks([]);
    if (!open) return;
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [open, refresh, generating]);

  const placeResult = (task: GenerationTask) => {
    const result = task.outputs;
    const imageUrl = result.image_url || result.video_url;
    if (!imageUrl || useProjectStore.getState().currentProject?.id !== projectId) return;
    const canvas = useCanvasStore.getState();
    canvas.pushSnapshot();
    const id = `history_${task.id}_${Date.now()}`;
    useCanvasStore.setState({ nodes: [...canvas.nodes, {
      id, type: 'imageCard', position: { x: 100, y: 100 },
      data: { ...mediaCardFields(result), assetId: result.asset_id, imageUrl, videoUrl: result.video_url, mediaType: result.video_url ? 'video' : 'image',
        width: result.width || 512, height: result.height || 512, provenance: result.provenance, label: result.provenance?.prompt || task.node_type },
    }], selectedNodeId: id });
    canvas.notifyCanvasChange();
  };

  return (
    <details className="absolute right-4 top-4 z-20 w-80 rounded-xl border border-slate-700 bg-slate-900 text-slate-200 shadow-xl" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className="cursor-pointer px-4 py-3 text-sm font-medium">Project generation history</summary>
      <div className="max-h-80 space-y-3 overflow-auto px-4 pb-4">
        <button type="button" className="rounded border border-slate-600 px-3 py-1 text-xs" onClick={() => void refresh()}>Refresh</button>
        {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
        {!error && tasks.length === 0 && <p className="text-sm text-slate-400">No recorded tasks in this project.</p>}
        {tasks.map((task) => (
          <article key={task.id} className="space-y-1 border-t border-slate-700 pt-2 text-sm">
            <p className="font-medium">{task.node_type} · {task.status}</p>
            <p className="truncate text-slate-400">{String(task.params.prompt || '')}</p>
            <time className="text-xs text-slate-400" dateTime={task.created_at}>{new Date(task.created_at).toLocaleString()}</time>
            {task.error && <p className="text-xs text-amber-300">{task.error}</p>}
            {(task.outputs.image_url || task.outputs.video_url) && <button type="button" className="block rounded border border-slate-600 px-2 py-1 text-xs" onClick={() => placeResult(task)}>Place result on canvas</button>}
          </article>
        ))}
      </div>
    </details>
  );
}
