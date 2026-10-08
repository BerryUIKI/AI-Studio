import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Node } from '@xyflow/react';
import { CanvasNodeData } from '../types/creative';
import { useCanvasStore } from '../stores/useCanvasStore';
import { useCreativeStore } from '../stores/useCreativeStore';

const card = (id: string): Node<CanvasNodeData> => ({
  id, type: 'imageCard', position: { x: 10, y: 20 },
  data: { assetId: id, imageUrl: `/api/v1/assets/${id}/content`, width: 8, height: 6 },
});

describe('Complete canvas transactions', () => {
  beforeEach(() => {
    useCanvasStore.setState({ nodes: [card('a'), card('b')], edges: [{ id: 'ab', source: 'a', target: 'b' }], selectedNodeId: 'a', past: [], future: [], isDragging: false });
    vi.restoreAllMocks();
  });

  it('restores deleted nodes, their relationships, edges and selection together', () => {
    useCanvasStore.getState().removeNode('a');
    expect(useCanvasStore.getState().edges).toEqual([]);
    useCanvasStore.getState().undo();
    expect(useCanvasStore.getState().nodes.map((node) => node.id)).toEqual(['a', 'b']);
    expect(useCanvasStore.getState().edges[0].id).toBe('ab');
    expect(useCanvasStore.getState().selectedNodeId).toBe('a');
    useCanvasStore.getState().redo();
    expect(useCanvasStore.getState().nodes.map((node) => node.id)).toEqual(['b']);
    expect(useCanvasStore.getState().edges).toEqual([]);
    expect(useCanvasStore.getState().selectedNodeId).toBeNull();
  });

  it('coalesces a drag gesture and restores its initial position', () => {
    for (const x of [20, 30, 40]) useCanvasStore.getState().onNodesChange([{ id: 'a', type: 'position', position: { x, y: 20 }, dragging: true }]);
    useCanvasStore.getState().onNodesChange([{ id: 'a', type: 'position', position: { x: 40, y: 20 }, dragging: false }]);
    expect(useCanvasStore.getState().past).toHaveLength(1);
    useCanvasStore.getState().undo();
    expect(useCanvasStore.getState().nodes[0].position.x).toBe(10);
    useCanvasStore.getState().redo();
    expect(useCanvasStore.getState().nodes[0].position.x).toBe(40);
  });

  it('creates one transaction when ReactFlow removes nodes then incident edges', () => {
    useCanvasStore.getState().onNodesChange([{ id: 'a', type: 'remove' }]);
    useCanvasStore.getState().onEdgesChange([{ id: 'ab', type: 'remove' }]);
    expect(useCanvasStore.getState().past).toHaveLength(1);
    useCanvasStore.getState().undo();
    expect(useCanvasStore.getState().edges).toHaveLength(1);
  });

  it('undoes an imported card without losing existing graph data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 'import', filename: 'image.png', width: 8, height: 6 }) }));
    await useCreativeStore.getState().uploadCanvasImage(new File(['fixture'], 'image.png', { type: 'image/png' }));
    expect(useCanvasStore.getState().nodes).toHaveLength(3);
    useCanvasStore.getState().undo();
    expect(useCanvasStore.getState().nodes).toHaveLength(2);
    expect(useCanvasStore.getState().edges).toHaveLength(1);
    useCanvasStore.getState().redo();
    expect(useCanvasStore.getState().nodes).toHaveLength(3);
    vi.unstubAllGlobals();
  });

  it('never restores a pending generation placeholder from history', () => {
    const pending = card('pending');
    pending.data = { ...pending.data, isGenerating: true };
    useCanvasStore.setState({ nodes: [...useCanvasStore.getState().nodes, pending] });
    useCanvasStore.getState().pushSnapshot();
    useCanvasStore.setState({ nodes: [card('done')] });
    useCanvasStore.getState().undo();
    expect(useCanvasStore.getState().nodes.map((node) => node.id)).toEqual(['a', 'b']);
  });

  it('undoes and redoes a completed generation as a single insertion', async () => {
    useCreativeStore.setState({ referenceImage: null, isGenerating: false });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true, task_id: 'task', asset_id: 'result', image_url: '/api/v1/assets/result/content', width: 8, height: 6 }) }));
    await useCreativeStore.getState().executeCreativeAction();
    expect(useCanvasStore.getState().nodes).toHaveLength(3);
    expect(useCanvasStore.getState().past).toHaveLength(1);
    useCanvasStore.getState().undo();
    expect(useCanvasStore.getState().nodes.map((node) => node.id)).toEqual(['a', 'b']);
    useCanvasStore.getState().redo();
    expect(useCanvasStore.getState().nodes[2].data.assetId).toBe('result');
    vi.unstubAllGlobals();
  });
});
