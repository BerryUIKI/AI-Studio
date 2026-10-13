import { GenerationTask } from '../types/task';

export async function* observeCreativeTask(taskId: string): AsyncGenerator<GenerationTask> {
  const terminal = new Set(['succeeded', 'cached', 'failed', 'cancelled', 'interrupted', 'outcome-unknown']);
  if (typeof EventSource !== 'undefined') {
    const events: GenerationTask[] = [];
    let wake: (() => void) | undefined;
    let disconnected = false;
    const source = new EventSource(`/api/v1/creative/tasks/${encodeURIComponent(taskId)}/events`);
    source.onmessage = (event) => {
      try { events.push(JSON.parse(event.data) as GenerationTask); }
      catch { disconnected = true; source.close(); }
      wake?.();
    };
    source.onerror = () => { disconnected = true; source.close(); wake?.(); };
    try {
      while (!disconnected || events.length > 0) {
        if (events.length === 0) await new Promise<void>((resolve) => { wake = resolve; });
        const task = events.shift();
        if (!task) continue;
        yield task;
        if (terminal.has(task.status)) return;
      }
    } finally { source.close(); }
  }
  // A stream outage falls back to retrieving the same task. Never submit again.
  for (;;) {
    const response = await fetch(`/api/v1/creative/tasks/${encodeURIComponent(taskId)}`, { signal: AbortSignal.timeout(30000) });
    if (!response.ok) throw new Error(`Task status unavailable (HTTP ${response.status}); task ${taskId} remains in history.`);
    const task: GenerationTask = await response.json();
    yield task;
    if (terminal.has(task.status)) return;
    await new Promise<void>((resolve) => setTimeout(resolve, 1000));
  }
}
