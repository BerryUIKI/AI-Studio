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
import { CustomNodeData, ExecutionStatus, NodeDefinition } from '../types/workflow';

interface CanvasState {
  nodes: Node<CustomNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;
  isExecuting: boolean;
  currentRunId: string | null;

  onNodesChange: (changes: NodeChange<Node<CustomNodeData>>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
  addNode: (definition: NodeDefinition, position?: { x: number; y: number }) => void;
  updateNodeParam: (nodeId: string, paramName: string, value: any) => void;
  setNodeStatus: (nodeId: string, status: ExecutionStatus) => void;
  setNodeOutput: (nodeId: string, output: Record<string, any>) => void;
  setSelectedNodeId: (nodeId: string | null) => void;
  clearCanvas: () => void;
  runWorkflow: (targetNodeId?: string) => Promise<void>;
  cancelRun: () => void;
}

export const useCanvasStore = create<CanvasState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  isExecuting: false,
  currentRunId: null,

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

  setNodeStatus: (nodeId, status) => {
    set({
      nodes: get().nodes.map((node) => {
        if (node.id !== nodeId) return node;
        return {
          ...node,
          data: {
            ...node.data,
            status,
          },
        };
      }),
    });
  },

  setNodeOutput: (nodeId, output) => {
    set({
      nodes: get().nodes.map((node) => {
        if (node.id !== nodeId) return node;
        return {
          ...node,
          data: {
            ...node.data,
            output,
          },
        };
      }),
    });
  },

  setSelectedNodeId: (nodeId) => set({ selectedNodeId: nodeId }),

  clearCanvas: () => set({ nodes: [], edges: [], selectedNodeId: null, isExecuting: false, currentRunId: null }),

  cancelRun: () => {
    const { currentRunId } = get();
    if (currentRunId) {
      fetch(`/api/v1/workflow/cancel/${currentRunId}`, { method: 'POST' }).catch(() => {});
      set({ isExecuting: false, currentRunId: null });
    }
  },

  runWorkflow: async (targetNodeId?: string) => {
    const { nodes, edges, setNodeStatus, setNodeOutput } = get();
    if (nodes.length === 0) return;

    const runId = `run_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    set({ isExecuting: true, currentRunId: runId });

    // If targeted execution, resolve ancestors to queue only relevant nodes
    const ancestorIds = new Set<string>();
    if (targetNodeId) {
      ancestorIds.add(targetNodeId);
      const queue = [targetNodeId];
      while (queue.length > 0) {
        const curr = queue.shift()!;
        edges
          .filter((e) => e.target === curr)
          .forEach((e) => {
            if (!ancestorIds.has(e.source)) {
              ancestorIds.add(e.source);
              queue.push(e.source);
            }
          });
      }
    }

    nodes.forEach((n) => {
      if (!targetNodeId || ancestorIds.has(n.id)) {
        setNodeStatus(n.id, 'queued');
      }
    });

    const runPayload = {
      run_id: runId,
      target_node_id: targetNodeId || null,
      graph: {
        nodes: nodes.map((n) => ({
          id: n.id,
          type: n.data.definition.type,
          params: n.data.params,
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source: e.source,
          source_handle: e.sourceHandle || 'output',
          target: e.target,
          target_handle: e.targetHandle || 'input',
        })),
      },
    };

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/workflow/run`;

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        ws.send(JSON.stringify(runPayload));
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'NODE_STATUS') {
            setNodeStatus(msg.node_id, msg.status);
          } else if (msg.type === 'NODE_OUTPUT') {
            setNodeOutput(msg.node_id, msg.output);
          } else if (msg.type === 'GRAPH_FINISHED') {
            set({ isExecuting: false, currentRunId: null });
          } else if (msg.type === 'RUN_CANCELLED') {
            set({ isExecuting: false, currentRunId: null });
          } else if (msg.type === 'ERROR' || msg.type === 'NODE_ERROR') {
            if (msg.node_id) {
              setNodeStatus(msg.node_id, 'error');
            }
            set({ isExecuting: false, currentRunId: null });
          }
        } catch {
          // ignore parsing error
        }
      };

      ws.onerror = () => {
        set({ isExecuting: false, currentRunId: null });
      };

      ws.onclose = () => {
        set({ isExecuting: false, currentRunId: null });
      };
    } catch {
      set({ isExecuting: false, currentRunId: null });
    }
  },
}));
