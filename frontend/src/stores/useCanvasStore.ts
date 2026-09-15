import { create } from 'zustand';
import {
  Connection,
  Edge,
  EdgeChange,
  Node,
  NodeChange,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
} from '@xyflow/react';
import { CustomNodeData, NodeDefinition } from '../types/workflow';

interface CanvasState {
  nodes: Node<CustomNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;

  onNodesChange: (changes: NodeChange<Node<CustomNodeData>>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
  addNode: (definition: NodeDefinition, position?: { x: number; y: number }) => void;
  updateNodeParam: (nodeId: string, paramName: string, value: any) => void;
  setSelectedNodeId: (nodeId: string | null) => void;
  clearCanvas: () => void;
}

export const useCanvasStore = create<CanvasState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,

  onNodesChange: (changes) => {
    set({
      nodes: applyNodeChanges(changes, get().nodes),
    });
  },

  onEdgesChange: (changes) => {
    set({
      edges: applyEdgeChanges(changes, get().edges),
    });
  },

  onConnect: (connection) => {
    set({
      edges: addEdge(
        {
          ...connection,
          animated: true,
          style: { stroke: '#6366f1', strokeWidth: 2 },
        },
        get().edges,
      ),
    });
  },

  addNode: (definition, position) => {
    const defaultParams: Record<string, any> = {};
    definition.parameters.forEach((param) => {
      defaultParams[param.name] = param.default;
    });

    const newNodeId = `node_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
    const pos = position || {
      x: 100 + get().nodes.length * 40,
      y: 100 + get().nodes.length * 40,
    };

    const newNode: Node<CustomNodeData> = {
      id: newNodeId,
      type: 'workflowNode',
      position: pos,
      data: {
        definition,
        params: defaultParams,
        status: 'idle',
      },
    };

    set({
      nodes: [...get().nodes, newNode],
      selectedNodeId: newNodeId,
    });
  },

  updateNodeParam: (nodeId, paramName, value) => {
    set({
      nodes: get().nodes.map((node) => {
        if (node.id !== nodeId) return node;
        return {
          ...node,
          data: {
            ...node.data,
            params: {
              ...node.data.params,
              [paramName]: value,
            },
          },
        };
      }),
    });
  },

  setSelectedNodeId: (nodeId) => set({ selectedNodeId: nodeId }),

  clearCanvas: () => set({ nodes: [], edges: [], selectedNodeId: null }),
}));
