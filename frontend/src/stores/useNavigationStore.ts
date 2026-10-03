import { create } from 'zustand';

export type ViewType = 'launcher' | 'canvas' | 'models' | 'comfyui' | 'webui' | 'settings';

interface NavigationState {
  activeView: ViewType;
  isRailCollapsed: boolean;
  viewHistory: ViewType[];
  
  setActiveView: (view: ViewType) => void;
  toggleRail: () => void;
  setRailCollapsed: (collapsed: boolean) => void;
}

export const useNavigationStore = create<NavigationState>((set, get) => ({
  activeView: 'launcher',
  isRailCollapsed: true,
  viewHistory: ['launcher'],

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
