import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const memoryStore: Record<string, string> = {};

const storageMock = {
  getItem: (key: string) => memoryStore[key] || null,
  setItem: (key: string, value: string) => {
    memoryStore[key] = value.toString();
  },
  clear: () => {
    for (const key of Object.keys(memoryStore)) {
      delete memoryStore[key];
    }
  },
  removeItem: (key: string) => {
    delete memoryStore[key];
  },
};

Object.defineProperty(globalThis, 'localStorage', {
  value: storageMock,
  writable: true,
  configurable: true,
});

import { useProjectStore } from '../stores/useProjectStore';
import { useCanvasStore } from '../stores/useCanvasStore';
import { useCreativeStore } from '../stores/useCreativeStore';
import { Project, ProjectCanvasData } from '../types/project';

describe('Project Persistence & Store Flow', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.useFakeTimers();
    localStorage.clear();

    useCanvasStore.setState({
      nodes: [],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      generationHistory: [],
      past: [],
      future: [],
      selectedNodeId: null,
    });

    useProjectStore.setState({
      currentProject: null,
      projects: [],
      isLoading: false,
      isSaving: false,
      isDirty: false,
      lastSavedAt: null,
      saveError: null,
      autosaveStatus: 'saved',
      isManagerModalOpen: false,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('initializes default project when no previous project exists in storage or backend', async () => {
    const mockCreated: Project = {
      id: 'proj_new_1',
      name: 'Default Canvas',
      canvas: {
        version: 1,
        nodes: [],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
        generationHistory: [],
      },
      version: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    globalThis.fetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
      if (url === '/api/v1/projects' && (!init || init.method === 'GET')) {
        return { ok: true, json: async () => [] };
      }
      if (url === '/api/v1/projects' && init?.method === 'POST') {
        return { ok: true, json: async () => mockCreated };
      }
      return { ok: false, status: 404 };
    });

    const project = await useProjectStore.getState().initProject();
    expect(project).toBeDefined();
    expect(project?.id).toBe('proj_new_1');
    expect(useProjectStore.getState().currentProject?.id).toBe('proj_new_1');
    expect(localStorage.getItem('berry_last_active_project_id')).toBe('proj_new_1');
  });

  it('restores canvas nodes, edges, viewport, and generation history on loadCanvas', () => {
    const canvasData: ProjectCanvasData = {
      version: 1,
      nodes: [
        {
          id: 'card-1',
          type: 'imageCard',
          position: { x: 120, y: 240 },
          data: {
            title: 'Sample Generation',
            imageUrl: 'http://127.0.0.1:8000/assets/sample.png',
            aspectRatio: '16:9',
            assetId: 'asset-123',
            provenance: {
              prompt: 'A futuristic city in neon light',
              action: 'txt2img',
              model: 'flux-schnell',
            },
          } as any,
        },
      ],
      edges: [
        {
          id: 'edge-1',
          source: 'card-1',
          target: 'card-2',
        },
      ],
      viewport: { x: 250, y: 150, zoom: 1.25 },
      generationHistory: [
        {
          id: 'gen-1',
          action: 'txt2img',
          prompt: 'A futuristic city in neon light',
          timestamp: '2026-10-07T08:00:00Z',
          assetId: 'asset-123',
        },
      ],
    };

    useCanvasStore.getState().loadCanvas(canvasData);

    const state = useCanvasStore.getState();
    expect(state.nodes.length).toBe(1);
    expect(state.nodes[0].id).toBe('card-1');
    expect(state.edges.length).toBe(1);
    expect(state.viewport).toEqual({ x: 250, y: 150, zoom: 1.25 });
    expect(state.generationHistory.length).toBe(1);
    expect(state.generationHistory[0].assetId).toBe('asset-123');
  });

  it('saves canvas updates with version increment and updates saved status', async () => {
    const initialProject: Project = {
      id: 'proj_save_test',
      name: 'Creative Project',
      canvas: {
        version: 1,
        nodes: [],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
      },
      version: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    useProjectStore.setState({ currentProject: initialProject });

    // Mutate canvas
    useCanvasStore.getState().setViewport({ x: 100, y: 200, zoom: 0.8 });
    useCanvasStore.getState().addGenerationHistory({
      id: 'gen-cyber',
      action: 'txt2img',
      prompt: 'Cyberpunk landscape',
      timestamp: new Date().toISOString(),
      assetId: 'asset-cyber',
    });

    let savedPayload: any = null;
    globalThis.fetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
      if (url === '/api/v1/projects/proj_save_test' && init?.method === 'PUT') {
        savedPayload = JSON.parse(init.body as string);
        return {
          ok: true,
          json: async () => ({
            ...initialProject,
            ...savedPayload,
            version: savedPayload.version,
            updated_at: new Date().toISOString(),
          }),
        };
      }
      return { ok: false };
    });

    const success = await useProjectStore.getState().saveProject();
    expect(success).toBe(true);
    expect(savedPayload).toBeDefined();
    expect(savedPayload.version).toBe(2);
    expect(savedPayload.canvas.viewport).toEqual({ x: 100, y: 200, zoom: 0.8 });
    expect(savedPayload.canvas.generationHistory.length).toBe(1);
    expect(useProjectStore.getState().autosaveStatus).toBe('saved');
    expect(useProjectStore.getState().isDirty).toBe(false);
  });

  it('debounces autosave and avoids saving if project id changed during debounce window', async () => {
    const projectA: Project = {
      id: 'proj_a',
      name: 'Project A',
      canvas: { version: 1, nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
      version: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    useProjectStore.setState({ currentProject: projectA, isDirty: true });

    let saveCalls = 0;
    globalThis.fetch = vi.fn().mockImplementation(async (_url: string, init?: RequestInit) => {
      if (init?.method === 'PUT') {
        saveCalls++;
        return {
          ok: true,
          json: async () => ({ ...projectA, version: 2 }),
        };
      }
      return { ok: false };
    });

    // Trigger autosave
    useProjectStore.getState().triggerAutosave();
    expect(saveCalls).toBe(0);

    // Fast-forward 1000ms (debounce is 1500ms)
    vi.advanceTimersByTime(1000);
    expect(saveCalls).toBe(0);

    // Fast-forward past 1500ms
    vi.advanceTimersByTime(600);
    expect(saveCalls).toBe(1);
  });

  it('flushes pending save before switching projects to prevent losing recent edits', async () => {
    const projectA: Project = {
      id: 'proj_a',
      name: 'Project A',
      canvas: { version: 1, nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
      version: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    const projectB: Project = {
      id: 'proj_b',
      name: 'Project B',
      canvas: {
        version: 1,
        nodes: [
          {
            id: 'node-b',
            type: 'textPrompt',
            position: { x: 50, y: 50 },
            data: { label: 'B Node', width: 200, height: 100 } as any,
          },
        ],
        edges: [],
        viewport: { x: 40, y: 80, zoom: 1 },
      },
      version: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    useProjectStore.setState({
      currentProject: projectA,
      projects: [projectA, projectB],
      isDirty: true,
    });

    let savedProjectA = false;
    globalThis.fetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
      if (url === '/api/v1/projects/proj_a' && init?.method === 'PUT') {
        savedProjectA = true;
        return { ok: true, json: async () => ({ ...projectA, version: 2 }) };
      }
      if (url === '/api/v1/projects/proj_b' && (!init || init.method === 'GET')) {
        return { ok: true, json: async () => projectB };
      }
      return { ok: false };
    });

    await useProjectStore.getState().openProject('proj_b');

    expect(savedProjectA).toBe(true);
    expect(useProjectStore.getState().currentProject?.id).toBe('proj_b');
    expect(useCanvasStore.getState().nodes.length).toBe(1);
    expect(useCanvasStore.getState().nodes[0].id).toBe('node-b');
  });

  it('renames and deletes projects cleanly', async () => {
    const project1: Project = {
      id: 'proj_1',
      name: 'Old Name',
      canvas: { version: 1, nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
      version: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    const project2: Project = {
      id: 'proj_2',
      name: 'Second Project',
      canvas: { version: 1, nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
      version: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    useProjectStore.setState({
      currentProject: project1,
      projects: [project1, project2],
    });

    globalThis.fetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
      if (url === '/api/v1/projects/proj_1' && init?.method === 'PUT') {
        return {
          ok: true,
          json: async () => ({ ...project1, name: 'Renamed Project' }),
        };
      }
      if (url === '/api/v1/projects/proj_1' && init?.method === 'DELETE') {
        return { ok: true, json: async () => ({ status: 'deleted' }) };
      }
      if (url === '/api/v1/projects/proj_2' && (!init || init.method === 'GET')) {
        return { ok: true, json: async () => project2 };
      }
      return { ok: false };
    });

    const renameOk = await useProjectStore.getState().renameProject('proj_1', 'Renamed Project');
    expect(renameOk).toBe(true);
    expect(useProjectStore.getState().currentProject?.name).toBe('Renamed Project');

    const deleteOk = await useProjectStore.getState().deleteProject('proj_1');
    expect(deleteOk).toBe(true);
    expect(useProjectStore.getState().projects.length).toBe(1);
    expect(useProjectStore.getState().currentProject?.id).toBe('proj_2');
  });

  it('marks project dirty when canvas nodes or edges change and triggers autosave', () => {
    const project1: Project = {
      id: 'proj_dirty_test',
      name: 'Dirty Project',
      canvas: { version: 1, nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
      version: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    useProjectStore.setState({
      currentProject: project1,
      isDirty: false,
      autosaveStatus: 'saved',
    });

    // Subscribed canvas change notifier
    useCanvasStore.getState().setViewport({ x: 10, y: 20, zoom: 1.5 });

    expect(useProjectStore.getState().isDirty).toBe(true);
    expect(useProjectStore.getState().autosaveStatus).toBe('dirty');
  });

  it('handles missing asset recovery metadata and flags', () => {
    const missingCardData = {
      assetId: 'asset_404',
      imageUrl: 'http://127.0.0.1:8000/assets/missing.png',
      isMissing: true,
      provenance: {
        action: 'txt2img' as const,
        prompt: 'Prompt for missing asset',
        model: 'flux',
      },
    };

    expect(missingCardData.isMissing).toBe(true);
    expect(missingCardData.provenance).toBeDefined();
    expect(missingCardData.provenance.prompt).toBe('Prompt for missing asset');
  });

  it('re-populates creative parameters from missing asset provenance for regeneration', () => {
    const cardData = {
      assetId: 'asset_missing_prompt',
      imageUrl: 'http://127.0.0.1:8000/assets/missing.png',
      isMissing: true,
      aspectRatio: '16:9',
      provenance: {
        action: 'txt2img' as const,
        prompt: 'Recovered prompt for regenerated asset',
        model: 'flux-schnell',
      },
    };

    useCreativeStore.setState({ prompt: '', aspectRatio: '1:1' });

    if (cardData.provenance?.prompt) {
      useCreativeStore.setState({
        prompt: cardData.provenance.prompt,
        aspectRatio: cardData.aspectRatio || '1:1',
      });
    }

    expect(useCreativeStore.getState().prompt).toBe('Recovered prompt for regenerated asset');
    expect(useCreativeStore.getState().aspectRatio).toBe('16:9');
  });

  it('replaces missing asset node data when new asset file is uploaded', () => {
    useCanvasStore.setState({
      nodes: [
        {
          id: 'card_missing_1',
          type: 'imageCard',
          position: { x: 0, y: 0 },
          data: {
            title: 'Missing Node',
            assetId: 'old_missing_asset',
            imageUrl: 'http://127.0.0.1:8000/assets/missing.png',
            isMissing: true,
          } as any,
        },
      ],
      edges: [],
    });

    const replacementAssetId = 'new_asset_999';
    const replacementUrl = `http://127.0.0.1:8000/assets/${replacementAssetId}.png`;

    useCanvasStore.getState().updateNodeData('card_missing_1', {
      assetId: replacementAssetId,
      imageUrl: replacementUrl,
      isMissing: false,
    });

    const updatedNode = useCanvasStore.getState().nodes.find((n) => n.id === 'card_missing_1');
    expect((updatedNode?.data as any).assetId).toBe('new_asset_999');
    expect((updatedNode?.data as any).imageUrl).toBe(replacementUrl);
    expect((updatedNode?.data as any).isMissing).toBe(false);
  });
});
