import { create } from 'zustand';

export type ViewType = 'launcher' | 'canvas' | 'models' | 'comfyui' | 'webui' | 'settings';
export type EngineViewType = 'comfyui' | 'webui';

interface NavigationState {
  activeView: ViewType;
  isRailCollapsed: boolean;
  viewHistory: ViewType[];
  selectedEngineIds: Partial<Record<EngineViewType, string>>;
  openEngineView: (type: EngineViewType, instanceId: string) => void;
  
  setActiveView: (view: ViewType) => void;
  toggleRail: () => void;
  setRailCollapsed: (collapsed: boolean) => void;
}

export const useNavigationStore = create<NavigationState>((set, get) => ({
  activeView: 'canvas',
  isRailCollapsed: true,
  viewHistory: ['canvas'],
  selectedEngineIds: {},
  openEngineView: (type, instanceId) => {
    set((state) => ({ selectedEngineIds: { ...state.selectedEngineIds, [type]: instanceId } }));
    get().setActiveView(type);
  },

  setActiveView: (view: ViewType) => {
    const current = get().activeView;
    if (current === view) return;
    set((state) => ({
      activeView: view,
      viewHistory: [...state.viewHistory.slice(-19), view],
    }));
  },

  toggleRail: () => {
    set((state) => ({ isRailCollapsed: !state.isRailCollapsed }));
  },

  setRailCollapsed: (collapsed: boolean) => {
    set({ isRailCollapsed: collapsed });
  },
}));
