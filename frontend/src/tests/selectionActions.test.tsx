// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { CreationDock } from '../components/canvas/CreationDock';
import { useCanvasStore } from '../stores/useCanvasStore';
import { useCreativeStore } from '../stores/useCreativeStore';
import { useCreationSetupStore } from '../stores/useCreationSetupStore';

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
  useCreativeStore.setState({ ...useCreativeStore.getInitialState(), isGenerating: false });
  useCreationSetupStore.setState({ models: [], providers: [], loading: false, error: null });
  useCanvasStore.setState({ ...useCanvasStore.getInitialState(), nodes: [
    { id: 'selected', type: 'imageCard', position: { x: 900, y: 500 }, selected: true,
      data: { imageUrl: '/api/v1/assets/fixture/content', width: 1024, height: 768, assetId: 'fixture' } },
    { id: 'other', type: 'imageCard', position: { x: 100, y: 100 },
      data: { imageUrl: '/api/v1/assets/other/content', width: 1024, height: 768 } },
  ], edges: [{ id: 'relationship', source: 'selected', target: 'other' }],
    selectedNodeId: 'selected', viewport: { x: 0, y: 0, zoom: 0.2 } });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); useCanvasStore.setState(useCanvasStore.getInitialState()); });

it('keeps selection actions in the dock and restores the complete delete transaction', () => {
  render(<CreationDock />);
  const actions = screen.getByRole('group', { name: 'Selected Asset' });
  expect(actions.className).not.toContain('absolute');
  fireEvent.click(within(actions).getByRole('button', { name: 'Delete (Backspace / Del)' }));
  expect(useCanvasStore.getState().nodes.map((node) => node.id)).toEqual(['other']);
  expect(useCanvasStore.getState().edges).toEqual([]);
  expect(useCanvasStore.getState().selectedNodeId).toBeNull();
  expect(screen.queryByRole('group', { name: 'Selected Asset' })).toBeNull();
  act(() => useCanvasStore.getState().undo());
  expect(useCanvasStore.getState().nodes.map((node) => node.id)).toEqual(['selected', 'other']);
  expect(useCanvasStore.getState().edges.map((edge) => edge.id)).toEqual(['relationship']);
  expect(useCanvasStore.getState().selectedNodeId).toBe('selected');
  expect(screen.getByRole('group', { name: 'Selected Asset' })).toBeTruthy();
});

it('only offers reference actions for the selected asset and hides the group after deselection', () => {
  render(<CreationDock />);
  fireEvent.click(within(screen.getByRole('group', { name: 'Selected Asset' })).getByRole('button', { name: 'Vary' }));
  expect(useCreativeStore.getState().referenceImage?.assetId).toBe('fixture');
  act(() => useCanvasStore.getState().setSelectedNodeId(null));
  expect(screen.queryByRole('group', { name: 'Selected Asset' })).toBeNull();
});
