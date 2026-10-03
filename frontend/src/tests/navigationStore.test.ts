import { describe, it, expect, beforeEach } from 'vitest';
import { useNavigationStore } from '../stores/useNavigationStore';

describe('useNavigationStore', () => {
  beforeEach(() => {
    useNavigationStore.setState({
      activeView: 'launcher',
      isRailCollapsed: true,
      viewHistory: ['launcher'],
    });
  });

  it('initializes with launcher as default view', () => {
    const state = useNavigationStore.getState();
    expect(state.activeView).toBe('launcher');
    expect(state.isRailCollapsed).toBe(true);
  });

  it('switches views and records history', () => {
    const store = useNavigationStore.getState();
    store.setActiveView('canvas');

    let state = useNavigationStore.getState();
    expect(state.activeView).toBe('canvas');
    expect(state.viewHistory).toEqual(['launcher', 'canvas']);

    store.setActiveView('comfyui');
    state = useNavigationStore.getState();
    expect(state.activeView).toBe('comfyui');
    expect(state.viewHistory).toEqual(['launcher', 'canvas', 'comfyui']);
  });

  it('does not duplicate history on repeated view switch', () => {
    const store = useNavigationStore.getState();
    store.setActiveView('canvas');
    store.setActiveView('canvas');

    const state = useNavigationStore.getState();
    expect(state.viewHistory).toEqual(['launcher', 'canvas']);
  });

  it('toggles rail collapse state', () => {
    const store = useNavigationStore.getState();
    expect(store.isRailCollapsed).toBe(true);

    store.toggleRail();
    expect(useNavigationStore.getState().isRailCollapsed).toBe(false);

    store.toggleRail();
    expect(useNavigationStore.getState().isRailCollapsed).toBe(true);
  });

  it('sets rail collapsed state explicitly', () => {
    const store = useNavigationStore.getState();
    store.setRailCollapsed(false);
    expect(useNavigationStore.getState().isRailCollapsed).toBe(false);

    store.setRailCollapsed(true);
    expect(useNavigationStore.getState().isRailCollapsed).toBe(true);
  });
});
