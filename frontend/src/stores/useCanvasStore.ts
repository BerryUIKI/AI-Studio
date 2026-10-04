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
import { CustomNodeData, ExecutionStatus, NodeDefinition, NodeOutputValue, NodeParamValue } from '../types/workflow';
import { CanvasNodeData, ImageCardData } from '../types/creative';

const isImageCardNode = (n: Node<CanvasNodeData>): n is Node<ImageCardData> => n.type === 'imageCard';
const isWorkflowNode = (n: Node<CanvasNodeData>): n is Node<CustomNodeData> => n.type === 'workflowNode' || !n.type;

interface CanvasState {
  nodes: Node<CanvasNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;
  isExecuting: boolean;
  currentRunId: string | null;
  past: Node<CanvasNodeData>[][];
  future: Node<CanvasNodeData>[][];

  onNodesChange: (changes: NodeChange<Node<CanvasNodeData>>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
  addNode: (definition: NodeDefinition, position?: { x: number; y: number }) => void;
  updateNodeParam: (nodeId: string, paramName: string, value: NodeParamValue) => void;
  setNodeStatus: (nodeId: string, status: ExecutionStatus) => void;
  setNodeOutput: (nodeId: string, output: Record<string, NodeOutputValue>) => void;
  setSelectedNodeId: (nodeId: string | null) => void;
  clearCanvas: () => void;
  runWorkflow: (targetNodeId?: string) => Promise<void>;
  cancelRun: () => void;
  pushSnapshot: () => void;
  undo: () => void;
  redo: () => void;
  removeNode: (nodeId: string) => void;
  duplicateNode: (nodeId: string) => void;
  arrangeBranchTree: (rootNodeId?: string) => void;
  addWorkspaceFrame: (label: string, position?: { x: number; y: number }, size?: { width: number; height: number }) => string;
}

export const useCanvasStore = create<CanvasState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  isExecuting: false,
  currentRunId: null,
  past: [],
  future: [],

  pushSnapshot: () => {
    const currentNodes = structuredClone(get().nodes);
    set((state) => ({
      past: [...state.past.slice(-24), currentNodes],
      future: [],
    }));
  },

  undo: () => {
    const { past, future, nodes } = get();
    if (past.length === 0) return;
    const previous = past[past.length - 1];
    const newPast = past.slice(0, -1);
    set({
      nodes: previous,
      past: newPast,
      future: [structuredClone(nodes), ...future],
    });
  },

  redo: () => {
    const { past, future, nodes } = get();
    if (future.length === 0) return;
    const next = future[0];
    const newFuture = future.slice(1);
    set({
      nodes: next,
      past: [...past, structuredClone(nodes)],
      future: newFuture,
    });
  },

  removeNode: (nodeId) => {
    get().pushSnapshot();
    const { nodes, edges, selectedNodeId } = get();
    set({
      nodes: nodes.filter((n) => n.id !== nodeId),
      edges: edges.filter((e) => e.source !== nodeId && e.target !== nodeId),
      selectedNodeId: selectedNodeId === nodeId ? null : selectedNodeId,
    });
  },

  duplicateNode: (nodeId) => {
    get().pushSnapshot();
    const { nodes } = get();
    const target = nodes.find((n) => n.id === nodeId);
    if (!target) return;

    const clonedId = `${target.type || 'node'}_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
    const clonedNode: Node<any> = {
      ...structuredClone(target),
      id: clonedId,
      position: {
        x: target.position.x + 40,
        y: target.position.y + 40,
      },
    };

    set({
      nodes: [...nodes, clonedNode],
      selectedNodeId: clonedId,
    });
  },

  arrangeBranchTree: (rootNodeId) => {
    const { nodes, selectedNodeId } = get();
    const targetId = rootNodeId || selectedNodeId;
    if (!targetId) return;

    const targetNode = nodes.find((n) => n.id === targetId);
    if (!targetNode || targetNode.type !== 'imageCard') return;

    get().pushSnapshot();

    // Map by assetId and source_asset_id
    const assetIdToNode = new Map<string, Node<ImageCardData>>();
    const parentToChildren = new Map<string, string[]>();

    nodes.filter(isImageCardNode).forEach((n) => {
      if (n.data?.assetId) {
        assetIdToNode.set(n.data.assetId, n);
      }
    });

    nodes.filter(isImageCardNode).forEach((n) => {
      const parentAssetId = n.data?.provenance?.source_asset_id;
      if (parentAssetId && assetIdToNode.has(parentAssetId)) {
        const list = parentToChildren.get(parentAssetId) || [];
        list.push(n.id);
        parentToChildren.set(parentAssetId, list);
      }
    });

    // Find root by tracing upwards
    let current: Node<CanvasNodeData> | undefined = targetNode;
    const visited = new Set<string>();
    while (current && isImageCardNode(current) && current.data?.provenance?.source_asset_id && !visited.has(current.id)) {
      visited.add(current.id);
      const parentNode = assetIdToNode.get(current.data.provenance.source_asset_id);
      if (parentNode) {
        current = parentNode;
      } else {
        break;
      }
    }
    const rootNode = current;

    // Layout hierarchy from root
    const updatedPositions = new Map<string, { x: number; y: number }>();
    const rootX = rootNode.position.x;
    const rootY = rootNode.position.y;
    updatedPositions.set(rootNode.id, { x: rootX, y: rootY });

    let currentYByDepth: Record<number, number> = { 0: rootY };

    const layoutSubtree = (node: Node<any>, depth: number) => {
      const assetId = node.data?.assetId;
      if (!assetId) return;
      const childrenIds = parentToChildren.get(assetId) || [];
      if (childrenIds.length === 0) return;

      const nextDepth = depth + 1;
      childrenIds.forEach((childId) => {
        const childNode = nodes.find((n) => n.id === childId);
        if (!childNode) return;

        const startY = currentYByDepth[nextDepth] ?? rootY;
        const x = rootX + nextDepth * 370;
        const y = startY;
        updatedPositions.set(childId, { x, y });
        currentYByDepth[nextDepth] = y + 430;

        layoutSubtree(childNode, nextDepth);
      });
    };

    layoutSubtree(rootNode, 0);

    set({
      nodes: nodes.map((n) => {
        const newPos = updatedPositions.get(n.id);
        if (newPos) {
          return { ...n, position: newPos };
        }
        return n;
      }),
    });
  },

  addWorkspaceFrame: (label, position, size) => {
    get().pushSnapshot();
    const frameId = `frame_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
    const pos = position || { x: 80, y: 80 };
    const dimensions = size || { width: 800, height: 500 };

    const newFrame: Node<any> = {
      id: frameId,
      type: 'workspaceFrame',
      position: pos,
      data: {
        label,
        width: dimensions.width,
        height: dimensions.height,
        color: 'indigo',
      },
      style: {
        width: dimensions.width,
        height: dimensions.height,
        zIndex: -1,
      },
    };

    set((state) => ({
      nodes: [newFrame, ...state.nodes],
      selectedNodeId: frameId,
    }));
    return frameId;
  },

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
    get().pushSnapshot();
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
        if (node.id !== nodeId || !isWorkflowNode(node)) return node;
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

  clearCanvas: () => {
    get().pushSnapshot();
    set({ nodes: [], edges: [], selectedNodeId: null, isExecuting: false, currentRunId: null });
  },

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
        nodes: nodes.filter(isWorkflowNode).map((n) => ({
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

    let reconnectAttempts = 0;
    const maxReconnectAttempts = 3;
    let heartbeatTimer: any = null;
    let isTerminated = false;

    const stopHeartbeat = () => {
      if (heartbeatTimer) {
        clearInterval(heartbeatTimer);
        heartbeatTimer = null;
      }
    };

    const cleanupExecution = () => {
      isTerminated = true;
      stopHeartbeat();
      set({ isExecuting: false, currentRunId: null });
    };

    const connect = () => {
      if (isTerminated || !get().isExecuting) return;

      try {
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          reconnectAttempts = 0;
          ws.send(JSON.stringify(runPayload));

          // Start client-side keepalive ping to maintain connection through proxies
          stopHeartbeat();
          heartbeatTimer = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              try {
                ws.send(JSON.stringify({ type: 'PING' }));
              } catch {
                // ignore send error
              }
            }
          }, 15000);
        };

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'PONG') {
              return;
            }
            if (msg.type === 'NODE_STATUS') {
              setNodeStatus(msg.node_id, msg.status);
            } else if (msg.type === 'NODE_OUTPUT') {
              setNodeOutput(msg.node_id, msg.output);
            } else if (msg.type === 'GRAPH_FINISHED') {
              cleanupExecution();
            } else if (msg.type === 'RUN_CANCELLED') {
              cleanupExecution();
            } else if (msg.type === 'ERROR' || msg.type === 'NODE_ERROR') {
              if (msg.node_id) {
                setNodeStatus(msg.node_id, 'error');
              }
              cleanupExecution();
            }
          } catch {
            // ignore parsing error
          }
        };

        ws.onerror = () => {
          stopHeartbeat();
        };

        ws.onclose = () => {
          stopHeartbeat();
          // If clean termination occurred or run concluded, do not reconnect
          if (isTerminated || !get().isExecuting) return;

          // Attempt reconnection if abruptly disconnected
          if (reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts += 1;
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), 4000);
            setTimeout(() => {
              if (get().isExecuting && !isTerminated) {
                connect();
              }
            }, delay);
          } else {
            cleanupExecution();
          }
        };
      } catch {
        cleanupExecution();
      }
    };

    connect();
  },
}));
