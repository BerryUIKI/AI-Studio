import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  NodeTypes,
  ReactFlowProvider,
  useReactFlow,
} from '@xyflow/react';
import { WorkflowNode } from './WorkflowNode';
import { ImageCardNode } from './ImageCardNode';
import { QuickAddMenu } from './QuickAddMenu';
import { useCanvasStore } from '../../stores/useCanvasStore';
import { useCreativeStore } from '../../stores/useCreativeStore';
import { NodeDefinition } from '../../types/workflow';

const nodeTypes: NodeTypes = {
  workflowNode: WorkflowNode,
  imageCard: ImageCardNode,
};

interface MenuState {
  isOpen: boolean;
  screenPosition: { x: number; y: number };
  flowPosition: { x: number; y: number };
}

function FlowCanvasInner() {
  const { nodes, edges, onNodesChange, onEdgesChange, onConnect, addNode } = useCanvasStore();
  const { uploadCanvasImage } = useCreativeStore();
  const { screenToFlowPosition } = useReactFlow();

  const [menuState, setMenuState] = useState<MenuState>({
    isOpen: false,
    screenPosition: { x: 0, y: 0 },
    flowPosition: { x: 0, y: 0 },
  });

  const lastClickRef = useRef<{ time: number; x: number; y: number }>({ time: 0, x: 0, y: 0 });
  const importPositionRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  // 2. Container context menu fallback (prevent browser menu on canvas background)
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
    [menuState.isOpen, closeMenu, openMenuAt]
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

  // 4. Keyboard shortcut: Shift + A or "/" to open quick add menu
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const targetTag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (targetTag === 'input' || targetTag === 'textarea') return;

      if ((e.shiftKey && (e.key === 'A' || e.key === 'a')) || e.key === '/') {
        e.preventDefault();
        const cx = window.innerWidth / 2;
        const cy = window.innerHeight / 2;
        openMenuAt(cx, cy);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [openMenuAt]);

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
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onPaneClick={handlePaneClick}
        onPaneContextMenu={handlePaneContextMenu}
        zoomOnDoubleClick={false}
        nodeTypes={nodeTypes}
        fitView
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
