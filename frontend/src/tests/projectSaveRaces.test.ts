import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { useCanvasStore } from '../stores/useCanvasStore';
import { useProjectStore } from '../stores/useProjectStore';
import type { Project, ProjectCanvasData } from '../types/project';

const project: Project = {
  id: 'race', name: 'Undo save race', version: 1,
  created_at: '2026-10-13T00:00:00Z', updated_at: '2026-10-13T00:00:00Z',
  canvas: { version: 1, nodes: [{ id: 'image', type: 'imageCard',
    position: { x: 100, y: 100 }, data: { imageUrl: '/api/v1/assets/fixture/content', width: 1024, height: 768 } }],
  edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
};
let unsubscribe: () => void;

beforeEach(() => {
  vi.useFakeTimers();
  useProjectStore.setState({ ...useProjectStore.getInitialState(), currentProject: project, projects: [project] });
  useCanvasStore.getState().loadCanvas(project.canvas);
  unsubscribe = useCanvasStore.getState().subscribeCanvasChange(() => useProjectStore.getState().markDirty());
});
afterEach(async () => {
  unsubscribe();
  useProjectStore.setState(useProjectStore.getInitialState());
  await useProjectStore.getState().flushPendingSave();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

it('saves an undo made while the deletion snapshot is still in flight', async () => {
  let finishFirst!: (response: Response) => void;
  const first = new Promise<Response>((resolve) => { finishFirst = resolve; });
  const payloads: { canvas: ProjectCanvasData; version: number; name: string }[] = [];
  vi.stubGlobal('fetch', vi.fn((_url: string, init: RequestInit) => {
    const payload = JSON.parse(String(init.body)) as (typeof payloads)[number];
    payloads.push(payload);
    if (payloads.length === 1) return first;
    return Promise.resolve(new Response(JSON.stringify({ ...project, ...payload }), { status: 200 }));
  }));
  useCanvasStore.getState().removeNode('image');
  const saving = useProjectStore.getState().saveProject();
  expect(payloads[0].canvas.nodes).toHaveLength(0);
  useCanvasStore.getState().undo();
  expect(useCanvasStore.getState().nodes).toHaveLength(1);
  finishFirst(new Response(JSON.stringify({ ...project, ...payloads[0] }), { status: 200 }));
  await saving;
  expect(useProjectStore.getState().isDirty).toBe(true);
  await vi.advanceTimersByTimeAsync(1600);
  expect(payloads).toHaveLength(2);
  expect(payloads[1].canvas.nodes[0].id).toBe('image');
  expect(useProjectStore.getState().currentProject?.canvas.nodes[0].id).toBe('image');
  expect(useProjectStore.getState().autosaveStatus).toBe('saved');
});
