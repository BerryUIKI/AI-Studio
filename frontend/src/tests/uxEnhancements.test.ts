import { describe, it, expect, beforeEach } from 'vitest';
import { useCanvasStore } from '../stores/useCanvasStore';
import { useCreativeStore } from '../stores/useCreativeStore';

describe('UX Enhancements Suite (Issues #33 - #38)', () => {
  beforeEach(() => {
    useCanvasStore.setState({
      nodes: [],
      edges: [],
      selectedNodeId: null,
      past: [],
      future: [],
    });

    useCreativeStore.setState({
      prompt: 'test prompt',
      negativePrompt: 'test negative',
      aspectRatio: '1:1',
      steps: 20,
      cfgScale: 7.0,
      denoise: 0.75,
      seed: -1,
      generationStage: 'Idle',
      generationProgress: 0,
      referenceImage: null,
    });
  });

  describe('Issue #33: Visual Lineage & Branching Tree Layout', () => {
    it('arranges branch tree hierarchically based on provenance source_asset_id', () => {
      const parentNode = {
        id: 'card-parent',
        type: 'imageCard',
        position: { x: 100, y: 100 },
        data: {
          assetId: 'asset-root',
          imageUrl: 'http://localhost/root.png',
          width: 512,
          height: 512,
        },
      };

      const child1 = {
        id: 'card-child-1',
        type: 'imageCard',
        position: { x: 50, y: 500 },
        data: {
          assetId: 'asset-child-1',
          imageUrl: 'http://localhost/child1.png',
          width: 512,
          height: 512,
          provenance: {
            action: 'img2img' as const,
            source_asset_id: 'asset-root',
            prompt: 'variation 1',
            model: 'sd',
            engine_id: 'managed_comfyui',
            seed: 1,
            steps: 20,
            cfg_scale: 7,
            dimensions: '512x512',
            created_at: new Date().toISOString(),
          },
        },
      };

      const child2 = {
        id: 'card-child-2',
        type: 'imageCard',
        position: { x: 50, y: 600 },
        data: {
          assetId: 'asset-child-2',
          imageUrl: 'http://localhost/child2.png',
          width: 512,
          height: 512,
          provenance: {
            action: 'img2img' as const,
            source_asset_id: 'asset-root',
            prompt: 'variation 2',
            model: 'sd',
            engine_id: 'managed_comfyui',
            seed: 2,
            steps: 20,
            cfg_scale: 7,
            dimensions: '512x512',
            created_at: new Date().toISOString(),
          },
        },
      };

      useCanvasStore.setState({ nodes: [parentNode, child1, child2] as any });

      // Run branch tree arrangement targeting root
      useCanvasStore.getState().arrangeBranchTree('card-parent');

      const updatedNodes = useCanvasStore.getState().nodes;
      const updatedParent = updatedNodes.find((n) => n.id === 'card-parent');
      const updatedChild1 = updatedNodes.find((n) => n.id === 'card-child-1');
      const updatedChild2 = updatedNodes.find((n) => n.id === 'card-child-2');

      expect(updatedParent?.position.x).toBe(100);
      expect(updatedParent?.position.y).toBe(100);

      // Children should be placed in the next column (X = 100 + 370 = 470)
      expect(updatedChild1?.position.x).toBe(470);
      expect(updatedChild2?.position.x).toBe(470);

      // Children should have distinct vertical Y coordinates
      expect(updatedChild2?.position.y).toBeGreaterThan(updatedChild1!.position.y);
    });
  });

  describe('Issue #34: Creation Dock Progressive Disclosure Parameters', () => {
    it('updates progressive generation controls (steps, cfg, denoise, seed)', () => {
      const store = useCreativeStore.getState();

      store.setSteps(35);
      store.setCfgScale(12.5);
      store.setDenoise(0.45);
      store.setSeed(987654);

      const state = useCreativeStore.getState();
      expect(state.steps).toBe(35);
      expect(state.cfgScale).toBe(12.5);
      expect(state.denoise).toBe(0.45);
      expect(state.seed).toBe(987654);
    });
  });

  describe('Issue #36: Canvas Undo/Redo & Node Operations', () => {
    it('supports undo and redo snapshots', () => {
      const nodeA = {
        id: 'node-a',
        type: 'imageCard',
        position: { x: 50, y: 50 },
        data: { imageUrl: 'a.png' },
      };

      useCanvasStore.setState({ nodes: [nodeA] as any });

      // Add a node and push snapshot
      useCanvasStore.getState().duplicateNode('node-a');
      expect(useCanvasStore.getState().nodes.length).toBe(2);

      // Undo
      useCanvasStore.getState().undo();
      expect(useCanvasStore.getState().nodes.length).toBe(1);

      // Redo
      useCanvasStore.getState().redo();
      expect(useCanvasStore.getState().nodes.length).toBe(2);
    });

    it('duplicates node with position offset', () => {
      const nodeA = {
        id: 'node-original',
        type: 'imageCard',
        position: { x: 100, y: 150 },
        data: { imageUrl: 'orig.png' },
      };

      useCanvasStore.setState({ nodes: [nodeA] as any });
      useCanvasStore.getState().duplicateNode('node-original');

      const nodes = useCanvasStore.getState().nodes;
      expect(nodes.length).toBe(2);

      const duplicated = nodes.find((n) => n.id !== 'node-original');
      expect(duplicated?.position.x).toBe(140);
      expect(duplicated?.position.y).toBe(190);
    });

    it('removes node and removes connected edges', () => {
      const nodeA = { id: 'node-1', type: 'imageCard', position: { x: 0, y: 0 }, data: {} };
      const nodeB = { id: 'node-2', type: 'imageCard', position: { x: 10, y: 10 }, data: {} };
      const edge = { id: 'edge-1-2', source: 'node-1', target: 'node-2' };

      useCanvasStore.setState({ nodes: [nodeA, nodeB] as any, edges: [edge] as any });

      useCanvasStore.getState().removeNode('node-1');

      const state = useCanvasStore.getState();
      expect(state.nodes.length).toBe(1);
      expect(state.nodes[0].id).toBe('node-2');
      expect(state.edges.length).toBe(0);
    });
  });

  describe('Issue #38: Spatial Agent Workspace Frames', () => {
    it('creates workspace frame node with custom label and dimensions', () => {
      const frameId = useCanvasStore.getState().addWorkspaceFrame(
        'Exploration Workspace',
        { x: 200, y: 300 },
        { width: 900, height: 600 }
      );

      const nodes = useCanvasStore.getState().nodes;
      const frame = nodes.find((n) => n.id === frameId);

      expect(frame).toBeDefined();
      expect(frame?.type).toBe('workspaceFrame');
      expect(frame?.data.label).toBe('Exploration Workspace');
      expect(frame?.position.x).toBe(200);
      expect(frame?.position.y).toBe(300);
      expect(frame?.data.width).toBe(900);
      expect(frame?.data.height).toBe(600);
    });
  });
});
