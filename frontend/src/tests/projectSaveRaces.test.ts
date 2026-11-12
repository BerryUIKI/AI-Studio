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

it('waits for both the active save and the restored snapshot before switching projects', async () => {
  const other: Project = { ...project, id: 'other', name: 'Other project' };
  let finishFirst!: (response: Response) => void;
  const first = new Promise<Response>((resolve) => { finishFirst = resolve; });
  const requests: string[] = [];
  const payloads: { canvas: ProjectCanvasData; version: number; name: string }[] = [];
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    requests.push(`${init?.method || 'GET'} ${url}`);
    if (init?.method === 'PUT') {
      const payload = JSON.parse(String(init.body)) as (typeof payloads)[number];
      payloads.push(payload);
      if (payloads.length === 1) return first;
      return Promise.resolve(new Response(JSON.stringify({ ...project, ...payload }), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify(url === '/api/v1/projects' ? [other] : other), { status: 200 }));
  }));
  useCanvasStore.getState().removeNode('image');
  const saving = useProjectStore.getState().saveProject();
  useCanvasStore.getState().undo();
  const opening = useProjectStore.getState().openProject('other');
  await vi.advanceTimersByTimeAsync(0);
  expect(requests).toEqual(['PUT /api/v1/projects/race']);
  finishFirst(new Response(JSON.stringify({ ...project, ...payloads[0] }), { status: 200 }));
  await Promise.all([saving, opening]);
  expect(payloads).toHaveLength(2);
  expect(payloads[1].canvas.nodes[0].id).toBe('image');
  expect(requests.slice(0, 3)).toEqual(['PUT /api/v1/projects/race', 'PUT /api/v1/projects/race', 'GET /api/v1/projects/other']);
  expect(useProjectStore.getState().currentProject?.id).toBe('other');
});

it.each(['open', 'create'])('retains the current canvas when its save fails before %s', async (operation) => {
  const requests: string[] = [];
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    requests.push(`${init?.method || 'GET'} ${url}`);
    return Promise.resolve(init?.method === 'PUT'
      ? new Response('Save failed', { status: 500 })
      : new Response(JSON.stringify({ ...project, id: 'other' }), { status: 200 }));
  }));
  useProjectStore.getState().markDirty();
  const result = operation === 'open' ? await useProjectStore.getState().openProject('other')
    : await useProjectStore.getState().createProject('Other');
  expect(result).toBe(operation === 'open' ? false : null);
  expect(requests).toEqual(['PUT /api/v1/projects/race']);
  expect(useProjectStore.getState().currentProject?.id).toBe('race');
  expect(useCanvasStore.getState().nodes[0].id).toBe('image');
});
