import { create } from 'zustand';
import { Project } from '../types/project';
import { useCanvasStore } from './useCanvasStore';

const STORAGE_ACTIVE_PROJECT_KEY = 'berry_last_active_project_id';
const AUTOSAVE_DEBOUNCE_MS = 1500;

let autosaveTimer: ReturnType<typeof setTimeout> | null = null;
let hasPendingChangesWhileSaving = false;

export interface ProjectState {
  currentProject: Project | null;
  projects: Project[];
  isLoading: boolean;
  isSaving: boolean;
  isDirty: boolean;
  lastSavedAt: string | null;
  saveError: string | null;
  autosaveStatus: 'saved' | 'saving' | 'dirty' | 'error';
  isManagerModalOpen: boolean;

  setIsManagerModalOpen: (open: boolean) => void;
  initProject: () => Promise<Project | null>;
  fetchProjects: () => Promise<Project[]>;
  createProject: (name?: string) => Promise<Project | null>;
  openProject: (projectId: string) => Promise<boolean>;
  saveProject: (projectId?: string) => Promise<boolean>;
  renameProject: (projectId: string, newName: string) => Promise<boolean>;
  deleteProject: (projectId: string) => Promise<boolean>;
  markDirty: () => void;
  triggerAutosave: () => void;
  flushPendingSave: () => Promise<boolean>;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  currentProject: null,
  projects: [],
  isLoading: false,
  isSaving: false,
  isDirty: false,
  lastSavedAt: null,
  saveError: null,
  autosaveStatus: 'saved',
  isManagerModalOpen: false,

  setIsManagerModalOpen: (open) => set({ isManagerModalOpen: open }),

  fetchProjects: async () => {
    try {
      const resp = await fetch('/api/v1/projects');
      if (!resp.ok) return [];
      const list: Project[] = await resp.json();
      set({ projects: list });
      return list;
    } catch (err) {
      console.error('Failed to list projects:', err);
      return [];
    }
  },

  initProject: async () => {
    set({ isLoading: true });
    try {
      // Subscribe useCanvasStore changes to automatically mark project dirty
      useCanvasStore.getState().subscribeCanvasChange(() => {
        get().markDirty();
      });

      const lastId = typeof localStorage !== 'undefined'
        ? localStorage.getItem(STORAGE_ACTIVE_PROJECT_KEY)
        : null;

      let projectToLoad: Project | null = null;

      if (lastId) {
        try {
          const resp = await fetch(`/api/v1/projects/${lastId}`);
          if (resp.ok) {
            projectToLoad = await resp.json();
          }
        } catch {
          // Fall through to list or create
        }
      }

      if (!projectToLoad) {
        const list = await get().fetchProjects();
        if (list.length > 0) {
          projectToLoad = list[0];
        }
      }

      if (!projectToLoad) {
        // Create initial project
        projectToLoad = await get().createProject('Untitled Project');
      }

      if (projectToLoad) {
        if (typeof localStorage !== 'undefined') {
          localStorage.setItem(STORAGE_ACTIVE_PROJECT_KEY, projectToLoad.id);
        }
        set({
          currentProject: projectToLoad,
          isDirty: false,
          autosaveStatus: 'saved',
          lastSavedAt: projectToLoad.updated_at,
          isLoading: false,
        });

        // Restore canvas layout, viewport, asset references, and generation history
        useCanvasStore.getState().loadCanvas(projectToLoad.canvas);
        await get().fetchProjects();
        return projectToLoad;
      }
    } catch (err) {
      console.error('Failed to init project:', err);
    } finally {
      set({ isLoading: false });
    }
    return null;
  },

  createProject: async (name = 'Untitled Project') => {
    // If current project has unsaved changes, flush them before switching
    if (get().isDirty && get().currentProject) {
      await get().flushPendingSave();
    }

    if (autosaveTimer) {
      clearTimeout(autosaveTimer);
      autosaveTimer = null;
    }

    try {
      const resp = await fetch('/api/v1/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          version: 1,
          canvas: {
            version: 1,
            nodes: [],
            edges: [],
            viewport: { x: 0, y: 0, zoom: 1 },
            generationHistory: [],
          },
        }),
      });

      if (!resp.ok) throw new Error(`Create project failed: HTTP ${resp.status}`);
      const newProj: Project = await resp.json();

      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(STORAGE_ACTIVE_PROJECT_KEY, newProj.id);
      }

      set((state) => ({
        currentProject: newProj,
        projects: [newProj, ...state.projects.filter((p) => p.id !== newProj.id)],
        isDirty: false,
        autosaveStatus: 'saved',
        lastSavedAt: newProj.updated_at,
      }));

      // Reset canvas for the new project
      useCanvasStore.getState().loadCanvas(newProj.canvas);
      return newProj;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Create project failed';
      set({ saveError: msg });
      return null;
    }
  },

  openProject: async (projectId: string) => {
    // Flush current project save if dirty
    if (get().isDirty && get().currentProject && get().currentProject?.id !== projectId) {
      await get().flushPendingSave();
    }

    if (autosaveTimer) {
      clearTimeout(autosaveTimer);
      autosaveTimer = null;
    }

    set({ isLoading: true });
    try {
      const resp = await fetch(`/api/v1/projects/${projectId}`);
      if (!resp.ok) throw new Error(`Open project failed: HTTP ${resp.status}`);
      const proj: Project = await resp.json();

      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(STORAGE_ACTIVE_PROJECT_KEY, proj.id);
      }

      set({
        currentProject: proj,
        isDirty: false,
        autosaveStatus: 'saved',
        lastSavedAt: proj.updated_at,
        isManagerModalOpen: false,
      });

      // Restore complete canvas state
      useCanvasStore.getState().loadCanvas(proj.canvas);
      await get().fetchProjects();
      return true;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Open project failed';
      set({ saveError: msg });
      return false;
    } finally {
      set({ isLoading: false });
    }
  },

  saveProject: async (projectId?: string) => {
    const targetId = projectId || get().currentProject?.id;
    if (!targetId) return false;

    // Prevent autosave from overwriting if active project has already switched
    if (get().currentProject?.id !== targetId) {
      return false;
    }

    const currentProj = get().currentProject;
    if (!currentProj) return false;

    // If a save is already in-flight for this project, queue follow-up save
    if (get().isSaving) {
      hasPendingChangesWhileSaving = true;
      return true;
    }

    set({ isSaving: true, autosaveStatus: 'saving', saveError: null });

    try {
      const canvasState = useCanvasStore.getState();
      const canvasPayload = {
        version: currentProj.version || 1,
        nodes: canvasState.nodes,
        edges: canvasState.edges,
        viewport: canvasState.viewport,
        generationHistory: canvasState.generationHistory,
      };

      const resp = await fetch(`/api/v1/projects/${targetId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: currentProj.name,
          version: currentProj.version || 1,
          canvas: canvasPayload,
        }),
      });

      if (!resp.ok) throw new Error(`Save failed with HTTP ${resp.status}`);
      const updated: Project = await resp.json();

      // Only update local state if target project is still current
      if (get().currentProject?.id === targetId) {
        set((state) => ({
          currentProject: {
            ...updated,
            // Keep current local nodes/edges if modifications were made while saving
            canvas: hasPendingChangesWhileSaving ? currentProj.canvas : updated.canvas,
          },
          projects: state.projects.map((p) => (p.id === updated.id ? updated : p)),
          isDirty: hasPendingChangesWhileSaving,
          autosaveStatus: hasPendingChangesWhileSaving ? 'dirty' : 'saved',
          lastSavedAt: updated.updated_at,
          isSaving: false,
        }));
      }

      // If changes occurred during save, trigger follow-up autosave
      if (hasPendingChangesWhileSaving) {
        hasPendingChangesWhileSaving = false;
        get().triggerAutosave();
      }

      return true;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Save failed';
      set({
        isSaving: false,
        autosaveStatus: 'error',
        saveError: msg,
      });
      return false;
    }
  },

  renameProject: async (projectId: string, newName: string) => {
    try {
      const resp = await fetch(`/api/v1/projects/${projectId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName }),
      });
      if (!resp.ok) return false;
      const updated: Project = await resp.json();

      set((state) => ({
        currentProject: state.currentProject?.id === projectId
          ? { ...state.currentProject, name: updated.name }
          : state.currentProject,
        projects: state.projects.map((p) => (p.id === projectId ? { ...p, name: updated.name } : p)),
      }));
      return true;
    } catch {
      return false;
    }
  },

  deleteProject: async (projectId: string) => {
    try {
      const resp = await fetch(`/api/v1/projects/${projectId}`, { method: 'DELETE' });
      if (!resp.ok) return false;

      const remaining = get().projects.filter((p) => p.id !== projectId);
      set({ projects: remaining });

      if (get().currentProject?.id === projectId) {
        if (remaining.length > 0) {
          await get().openProject(remaining[0].id);
        } else {
          await get().createProject('Untitled Project');
        }
      }
      return true;
    } catch {
      return false;
    }
  },

  markDirty: () => {
    // If not dirty, mark dirty and schedule debounced autosave
    set({ isDirty: true, autosaveStatus: 'dirty' });
    get().triggerAutosave();
  },

  triggerAutosave: () => {
    if (autosaveTimer) {
      clearTimeout(autosaveTimer);
      autosaveTimer = null;
    }

    const targetId = get().currentProject?.id;
    if (!targetId) return;

    autosaveTimer = setTimeout(() => {
      autosaveTimer = null;
      // Guard against saving after project switched
      if (get().currentProject?.id === targetId && get().isDirty) {
        get().saveProject(targetId);
      }
    }, AUTOSAVE_DEBOUNCE_MS);
  },

  flushPendingSave: async () => {
    if (autosaveTimer) {
      clearTimeout(autosaveTimer);
      autosaveTimer = null;
    }
    const currentId = get().currentProject?.id;
    if (currentId && get().isDirty) {
      return await get().saveProject(currentId);
    }
    return true;
  },
}));
