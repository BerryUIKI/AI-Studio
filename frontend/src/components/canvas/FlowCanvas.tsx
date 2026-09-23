import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  NodeTypes,
} from '@xyflow/react';
import { WorkflowNode } from './WorkflowNode';
import { ImageCardNode } from './ImageCardNode';
import { useCanvasStore } from '../../stores/useCanvasStore';

const nodeTypes: NodeTypes = {
  workflowNode: WorkflowNode,
  imageCard: ImageCardNode,
};

export function FlowCanvas() {
  const { nodes, edges, onNodesChange, onEdgesChange, onConnect } = useCanvasStore();

  return (
    <div className="w-full h-full relative bg-slate-950">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
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
    </div>
  );
}
