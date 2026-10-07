import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  NodeTypes,
  ReactFlowProvider,
  useReactFlow,
  Edge,
} from '@xyflow/react';
import { WorkflowNode } from './WorkflowNode';
import { ImageCardNode } from './ImageCardNode';
import { WorkspaceFrameNode } from './WorkspaceFrameNode';
import { QuickAddMenu } from './QuickAddMenu';
import { CanvasAgentPrompt } from '../agent/CanvasAgentPrompt';
import { useCanvasStore } from '../../stores/useCanvasStore';
import { useCreativeStore } from '../../stores/useCreativeStore';
import { NodeDefinition } from '../../types/workflow';
import { ImageCardData } from '../../types/creative';
import { useProjectStore } from '../../stores/useProjectStore';

const nodeTypes: NodeTypes = {
  workflowNode: WorkflowNode,
  imageCard: ImageCardNode,
  workspaceFrame: WorkspaceFrameNode,
};

interface MenuState {
  isOpen: boolean;
  screenPosition: { x: number; y: number };
  flowPosition: { x: number; y: number };
}

function FlowCanvasInner() {
  const {
    nodes,
    edges,
    viewport,
    setViewport: setViewportInStore,
    selectedNodeId,
    onNodesChange,
    onEdgesChange,
    onConnect,
    addNode,
    removeNode,
    duplicateNode,
    undo,
    redo,
    setSelectedNodeId,
  } = useCanvasStore();

  const { uploadCanvasImage } = useCreativeStore();
  const { screenToFlowPosition, setViewport } = useReactFlow();
  const currentProjectId = useProjectStore((s) => s.currentProject?.id);

  // Synchronize ReactFlow viewport when project loads
  useEffect(() => {
    if (viewport && typeof viewport.x === 'number' && typeof viewport.zoom === 'number') {
      setViewport(viewport, { duration: 0 });
    }
  }, [currentProjectId, setViewport]);

  // Global Ctrl+S shortcut to save project
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        useProjectStore.getState().saveProject();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const [menuState, setMenuState] = useState<MenuState>({
    isOpen: false,
    screenPosition: { x: 0, y: 0 },
    flowPosition: { x: 0, y: 0 },
  });

  const [agentPromptState, setAgentPromptState] = useState<{
    isOpen: boolean;
    screenPosition: { x: number; y: number };
    flowPosition: { x: number; y: number };
  }>({
    isOpen: false,
    screenPosition: { x: 0, y: 0 },
    flowPosition: { x: 0, y: 0 },
  });

  const lastClickRef = useRef<{ time: number; x: number; y: number }>({ time: 0, x: 0, y: 0 });
  const importPositionRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const mousePosRef = useRef<{ x: number; y: number }>({
    x: window.innerWidth / 2,
    y: window.innerHeight / 2,
  });
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Track global mouse position for paste & slash actions
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      mousePosRef.current = { x: e.clientX, y: e.clientY };
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  // Compute dynamic Ghost Lineage Edges (Issue #33)
  const lineageEdges = useMemo(() => {
    if (!selectedNodeId) return [];
    const selectedNode = nodes.find((n) => n.id === selectedNodeId);
    if (!selectedNode || selectedNode.type !== 'imageCard') return [];

    const cardData = selectedNode.data as unknown as ImageCardData;
    const currentAssetId = cardData?.assetId;
    const parentAssetId = cardData?.provenance?.source_asset_id;

    const dynamicEdges: Edge[] = [];

    // Connect to parent node if on canvas
    if (parentAssetId) {
      const parentNode = nodes.find((n) => {
        const d = n.data as unknown as ImageCardData;
        return d?.assetId === parentAssetId;
      });
      if (parentNode) {
        dynamicEdges.push({
          id: `lineage_${parentNode.id}_${selectedNode.id}`,
          source: parentNode.id,
          target: selectedNode.id,
          animated: true,
          style: { stroke: '#818cf8', strokeWidth: 2.5, strokeDasharray: '5 5' },
        });
      }
    }

    // Connect to child nodes if on canvas
    if (currentAssetId) {
      const childrenNodes = nodes.filter((n) => {
        if (n.id === selectedNode.id) return false;
        const d = n.data as unknown as ImageCardData;
        return d?.provenance?.source_asset_id === currentAssetId;
      });
      childrenNodes.forEach((childNode) => {
        dynamicEdges.push({
          id: `lineage_${selectedNode.id}_${childNode.id}`,
          source: selectedNode.id,
          target: childNode.id,
          animated: true,
          style: { stroke: '#818cf8', strokeWidth: 2.5, strokeDasharray: '5 5' },
        });
      });
    }

    return dynamicEdges;
  }, [selectedNodeId, nodes]);

  const combinedEdges = useMemo(() => [...edges, ...lineageEdges], [edges, lineageEdges]);

  const openMenuAt = useCallback(
    (clientX: number, clientY: number) => {
      const flowPos = screenToFlowPosition({ x: clientX, y: clientY });
      setMenuState({
        isOpen: true,
        screenPosition: { x: clientX, y: clientY },
        flowPosition: flowPos,
      });
    },
    [screenToFlowPosition]
  );

  const closeMenu = useCallback(() => {
    setMenuState((prev) => ({ ...prev, isOpen: false }));
  }, []);

  // 1. Right-click on pane
  const handlePaneContextMenu = useCallback(
    (event: React.MouseEvent | MouseEvent) => {
      event.preventDefault();
      const clientX = 'clientX' in event ? event.clientX : 0;
      const clientY = 'clientY' in event ? event.clientY : 0;
      openMenuAt(clientX, clientY);
    },
    [openMenuAt]
  );

  // 2. Container context menu fallback
  const handleContainerContextMenu = useCallback(
    (event: React.MouseEvent) => {
      const target = event.target as HTMLElement;
      if (
        target.closest('.react-flow__node') ||
        target.closest('.react-flow__edge') ||
        target.closest('.react-flow__controls') ||
        target.closest('.react-flow__minimap')
      ) {
        return;
      }
      event.preventDefault();
      openMenuAt(event.clientX, event.clientY);
    },
    [openMenuAt]
  );

  // 3. Double-click detection on pane
  const handlePaneClick = useCallback(
    (event: React.MouseEvent) => {
      if (menuState.isOpen) {
        closeMenu();
        return;
      }
      if (agentPromptState.isOpen) {
        setAgentPromptState((prev) => ({ ...prev, isOpen: false }));
      }

      const now = Date.now();
      const dist = Math.hypot(
        event.clientX - lastClickRef.current.x,
        event.clientY - lastClickRef.current.y
      );

      if (now - lastClickRef.current.time < 350 && dist < 25) {
        openMenuAt(event.clientX, event.clientY);
      }
      lastClickRef.current = { time: now, x: event.clientX, y: event.clientY };
    },
    [menuState.isOpen, agentPromptState.isOpen, closeMenu, openMenuAt]
  );

  // Double click event on wrapper
  const handleContainerDoubleClick = useCallback(
    (event: React.MouseEvent) => {
      const target = event.target as HTMLElement;
      if (
        target.closest('.react-flow__node') ||
        target.closest('.react-flow__edge') ||
        target.closest('.react-flow__controls') ||
        target.closest('.react-flow__minimap')
      ) {
        return;
      }
      openMenuAt(event.clientX, event.clientY);
    },
    [openMenuAt]
  );

  // 4. Native Clipboard Paste (Ctrl+V) & Power-User Shortcuts (Issue #36 & Issue #38)
  useEffect(() => {
    const handlePaste = (e: ClipboardEvent) => {
      const targetTag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (targetTag === 'input' || targetTag === 'textarea') return;

      const items = e.clipboardData?.items;
      if (!items) return;

      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.type.startsWith('image/')) {
          const file = item.getAsFile();
          if (file) {
            e.preventDefault();
            const flowPos = screenToFlowPosition(mousePosRef.current);
            uploadCanvasImage(file, flowPos);
            break;
          }
        }
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      const targetTag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (targetTag === 'input' || targetTag === 'textarea') return;

      // Delete / Backspace: Remove selected node
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedNodeId) {
          e.preventDefault();
          removeNode(selectedNodeId);
        }
      }

      // Ctrl + D / Cmd + D: Duplicate selected node
      if ((e.ctrlKey || e.metaKey) && (e.key === 'd' || e.key === 'D')) {
        if (selectedNodeId) {
          e.preventDefault();
          duplicateNode(selectedNodeId);
        }
      }

      // Ctrl + Z: Undo
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && (e.key === 'z' || e.key === 'Z')) {
        e.preventDefault();
        undo();
      }

      // Ctrl + Y or Ctrl + Shift + Z: Redo
      if (
        ((e.ctrlKey || e.metaKey) && (e.key === 'y' || e.key === 'Y')) ||
        ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'z' || e.key === 'Z'))
      ) {
        e.preventDefault();
        redo();
      }

      // "/" key: Spatial Agent quick prompt trigger (Issue #38)
      if (e.key === '/') {
        e.preventDefault();
        const flowPos = screenToFlowPosition(mousePosRef.current);
        setAgentPromptState({
          isOpen: true,
          screenPosition: mousePosRef.current,
          flowPosition: flowPos,
        });
      }

      // Shift + A: Quick add node menu
      if (e.shiftKey && (e.key === 'A' || e.key === 'a')) {
        e.preventDefault();
        openMenuAt(mousePosRef.current.x, mousePosRef.current.y);
      }
    };

    window.addEventListener('paste', handlePaste);
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('paste', handlePaste);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [
    selectedNodeId,
    removeNode,
    duplicateNode,
    undo,
    redo,
    screenToFlowPosition,
    uploadCanvasImage,
    openMenuAt,
  ]);

  const handleSelectNode = useCallback(
    (nodeDef: NodeDefinition, pos: { x: number; y: number }) => {
      addNode(nodeDef, pos);
    },
    [addNode]
  );

  const handleImportImage = useCallback((pos: { x: number; y: number }) => {
    importPositionRef.current = pos;
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        uploadCanvasImage(file, importPositionRef.current);
        e.target.value = '';
      }
    },
    [uploadCanvasImage]
  );

  return (
    <div
      className="w-full h-full relative bg-slate-950"
      onContextMenu={handleContainerContextMenu}
      onDoubleClick={handleContainerDoubleClick}
    >
      {/* Hidden file input for localized image import */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept="image/*"
        className="hidden"
      />

      <ReactFlow
        nodes={nodes}
        edges={combinedEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onPaneClick={handlePaneClick}
        onPaneContextMenu={handlePaneContextMenu}
        onNodeClick={(_, node) => setSelectedNodeId(node.id)}
        onMoveEnd={(_, vp) => {
          setViewportInStore(vp);
        }}
        zoomOnDoubleClick={false}
        nodeTypes={nodeTypes}
        fitView={nodes.length === 0}
        defaultViewport={viewport}
        className="dark"
        minZoom={0.2}
        maxZoom={2.5}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#334155" />
        <Controls className="bg-slate-900 border-slate-800 fill-slate-300" />
        <MiniMap
          nodeColor="#6366f1"
          maskColor="rgba(15, 23, 42, 0.75)"
          className="bg-slate-900/80 border border-slate-800 rounded-lg overflow-hidden"
        />
      </ReactFlow>

      {/* Quick Add / Context Menu */}
      <QuickAddMenu
        isOpen={menuState.isOpen}
        screenPosition={menuState.screenPosition}
        flowPosition={menuState.flowPosition}
        onClose={closeMenu}
        onSelectNode={handleSelectNode}
        onImportImage={handleImportImage}
      />

      {/* Spatial Agent Slash Prompt (Issue #38) */}
      <CanvasAgentPrompt
        isOpen={agentPromptState.isOpen}
        position={agentPromptState.screenPosition}
        flowPosition={agentPromptState.flowPosition}
        onClose={() => setAgentPromptState((prev) => ({ ...prev, isOpen: false }))}
      />
    </div>
  );
}

export function FlowCanvas() {
  return (
    <ReactFlowProvider>
      <FlowCanvasInner />
    </ReactFlowProvider>
  );
}
