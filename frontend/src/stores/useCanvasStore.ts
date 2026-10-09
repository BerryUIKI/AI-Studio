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
import { GenerationHistoryItem, ProjectCanvasData, ProjectViewport } from '../types/project';
import { useProjectStore } from './useProjectStore';

interface WorkflowStreamEvent {
  type: string;
  run_id?: string;
  sequence?: number;
  node_id: string;
  status: ExecutionStatus;
  output: Record<string, NodeOutputValue>;
}

const isImageCardNode = (n: Node<CanvasNodeData>): n is Node<ImageCardData> => n.type === 'imageCard';
const isWorkflowNode = (n: Node<CanvasNodeData>): n is Node<CustomNodeData> => n.type === 'workflowNode' || !n.type;

const canvasChangeListeners = new Set<() => void>();

interface CanvasSnapshot {
  nodes: Node<CanvasNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;
}

function snapshotCanvas(state: CanvasState): CanvasSnapshot {
  // Pending cards are transient; undo must never restore an abandoned spinner.
  const nodes = state.nodes.filter((node) => !isImageCardNode(node) || !node.data.isGenerating);
  return structuredClone({ nodes, edges: state.edges, selectedNodeId: nodes.some((node) => node.id === state.selectedNodeId) ? state.selectedNodeId : null });
}

interface CanvasState {
  nodes: Node<CanvasNodeData>[];
  edges: Edge[];
  viewport: ProjectViewport;
  generationHistory: GenerationHistoryItem[];
  selectedNodeId: string | null;
  isExecuting: boolean;
  currentRunId: string | null;
  past: CanvasSnapshot[];
  future: CanvasSnapshot[];
  isDragging: boolean;

  setViewport: (viewport: ProjectViewport) => void;
  addGenerationHistory: (item: GenerationHistoryItem) => void;
  loadCanvas: (canvas: Partial<ProjectCanvasData>) => void;
  subscribeCanvasChange: (listener: () => void) => () => void;
  notifyCanvasChange: () => void;
  onNodesChange: (changes: NodeChange<Node<CanvasNodeData>>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
  addNode: (definition: NodeDefinition, position?: { x: number; y: number }) => void;
  updateNodeData: (nodeId: string, data: Record<string, any>) => void;
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
  viewport: { x: 0, y: 0, zoom: 1 },
  generationHistory: [],
  selectedNodeId: null,
  isExecuting: false,
  currentRunId: null,
  past: [],
  future: [],
  isDragging: false,

  subscribeCanvasChange: (listener: () => void) => {
    canvasChangeListeners.add(listener);
    return () => {
      canvasChangeListeners.delete(listener);
    };
  },

  notifyCanvasChange: () => {
    canvasChangeListeners.forEach((fn) => {
      try {
        fn();
      } catch (err) {
        console.error('Error in canvas change listener:', err);
      }
    });
  },

  setViewport: (viewport: ProjectViewport) => {
    set({ viewport });
    get().notifyCanvasChange();
  },

  addGenerationHistory: (item: GenerationHistoryItem) => {
    set((state) => ({
      generationHistory: [item, ...state.generationHistory.slice(0, 99)],
    }));
    get().notifyCanvasChange();
  },

  loadCanvas: (data: Partial<ProjectCanvasData>) => {
    set({
      nodes: data.nodes ? structuredClone(data.nodes) : [],
      edges: data.edges ? structuredClone(data.edges) : [],
      viewport: data.viewport ? structuredClone(data.viewport) : { x: 0, y: 0, zoom: 1 },
      generationHistory: data.generationHistory ? structuredClone(data.generationHistory) : [],
      selectedNodeId: null,
      past: [],
      future: [],
      isDragging: false,
    });
  },

  pushSnapshot: () => {
    const currentCanvas = snapshotCanvas(get());
    set((state) => ({
      past: [...state.past.slice(-24), currentCanvas],
      future: [],
    }));
  },

  undo: () => {
    const { past, future } = get();
    if (past.length === 0) return;
    const previous = past[past.length - 1];
    const newPast = past.slice(0, -1);
    set({
      ...structuredClone(previous),
      past: newPast,
      future: [snapshotCanvas(get()), ...future],
      isDragging: false,
    });
    get().notifyCanvasChange();
  },

  redo: () => {
    const { past, future } = get();
    if (future.length === 0) return;
    const next = future[0];
    const newFuture = future.slice(1);
    set({
      ...structuredClone(next),
      past: [...past, snapshotCanvas(get())],
      future: newFuture,
      isDragging: false,
    });
    get().notifyCanvasChange();
  },

  removeNode: (nodeId) => {
    get().pushSnapshot();
    const { nodes, edges, selectedNodeId } = get();
    set({
      nodes: nodes.filter((n) => n.id !== nodeId),
      edges: edges.filter((e) => e.source !== nodeId && e.target !== nodeId),
      selectedNodeId: selectedNodeId === nodeId ? null : selectedNodeId,
    });
    get().notifyCanvasChange();
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
    get().notifyCanvasChange();
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
    get().notifyCanvasChange();
    return frameId;
  },

  onNodesChange: (changes) => {
    const structural = changes.some((change) => change.type === 'add' || change.type === 'replace' ||
      (change.type === 'remove' && get().nodes.some((node) => node.id === change.id)));
    const movement = changes.filter((change) => (change.type === 'position' && change.position) ||
      (change.type === 'dimensions' && change.resizing !== undefined));
    if (structural || (movement.length > 0 && !get().isDragging)) get().pushSnapshot();
    const removed = new Set(changes.filter((change) => change.type === 'remove').map((change) => change.id));
    set({
      nodes: applyNodeChanges(changes, get().nodes),
      edges: get().edges.filter((edge) => !removed.has(edge.source) && !removed.has(edge.target)),
      selectedNodeId: removed.has(get().selectedNodeId || '') ? null : get().selectedNodeId,
      isDragging: movement.length ? movement.some((change) => (change.type === 'position' && change.dragging) ||
        (change.type === 'dimensions' && change.resizing)) : get().isDragging,
    });
    if (changes.some((c) => c.type !== 'select')) {
      get().notifyCanvasChange();
    }
  },

  onEdgesChange: (changes) => {
    if (changes.some((change) => change.type === 'add' || change.type === 'replace' ||
      (change.type === 'remove' && get().edges.some((edge) => edge.id === change.id)))) get().pushSnapshot();
    set({
      edges: applyEdgeChanges(changes, get().edges),
    });
    if (changes.some((c) => c.type !== 'select')) {
      get().notifyCanvasChange();
    }
  },

  onConnect: (connection) => {
    get().pushSnapshot();
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
    get().notifyCanvasChange();
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
    get().notifyCanvasChange();
  },

  updateNodeData: (nodeId, data) => {
    set({
      nodes: get().nodes.map((node) => {
        if (node.id !== nodeId) return node;
        return {
          ...node,
          data: {
            ...node.data,
            ...data,
          },
        };
      }),
    });
    get().notifyCanvasChange();
  },

  updateNodeParam: (nodeId, paramName, value) => {
    get().pushSnapshot();
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
    get().notifyCanvasChange();
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
    get().notifyCanvasChange();
  },

  cancelRun: () => {
    const { currentRunId } = get();
    if (currentRunId) {
      fetch(`/api/v1/workflow/cancel/${currentRunId}`, { method: 'POST' }).catch(() => {});
      // Keep the subscription and run identity until the server records an outcome.
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
      project_id: useProjectStore.getState().currentProject?.id,
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
    let isTerminated = false;
    let lastSequence = 0;
    let socket: WebSocket | null = null;

    const cleanupExecution = () => {
      isTerminated = true;
      socket?.close();
      if (get().currentRunId === runId) set({ isExecuting: false, currentRunId: null });
    };

    const connect = () => {
      if (isTerminated || get().currentRunId !== runId) return;

      try {
        const ws = new WebSocket(wsUrl);
        socket = ws;

        ws.onopen = () => {
          ws.send(JSON.stringify({ type: 'SUBSCRIBE', run_id: runId, after_sequence: lastSequence }));
        };

        ws.onmessage = (event) => {
          try {
            const msg: WorkflowStreamEvent = JSON.parse(event.data);
            if (get().currentRunId !== runId || msg.run_id !== runId) return;
            if (msg.sequence !== undefined && msg.sequence <= lastSequence) return;
            if (msg.sequence !== undefined) lastSequence = msg.sequence;
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
              if (msg.type === 'ERROR') cleanupExecution();
            }
          } catch {
            // ignore parsing error
          }
        };

        ws.onclose = () => {
          // If clean termination occurred or run concluded, do not reconnect
          if (isTerminated || get().currentRunId !== runId) return;

          // Attempt reconnection if abruptly disconnected
          if (reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts += 1;
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), 4000);
            setTimeout(() => {
              if (get().currentRunId === runId && !isTerminated) {
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

    try {
      const response = await fetch('/api/v1/workflow/submit', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(runPayload),
      });
      if (!response.ok) throw new Error(`Workflow submission failed (${response.status})`);
      connect();
    } catch {
      cleanupExecution();
    }
  },
}));
