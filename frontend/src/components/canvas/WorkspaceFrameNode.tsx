import { memo } from 'react';
import { NodeProps } from '@xyflow/react';
import { Layers, Trash2, Sparkles } from 'lucide-react';
import { WorkspaceFrameData } from '../../types/creative';
import { useCanvasStore } from '../../stores/useCanvasStore';

export const WorkspaceFrameNode = memo(({ id, data, selected }: NodeProps) => {
  const frameData = data as unknown as WorkspaceFrameData;
  const { removeNode, nodes } = useCanvasStore();

  const width = frameData.width || 820;
  const height = frameData.height || 520;

  // Count items conceptually inside or assigned to this frame
  const containedCount = nodes.filter(
    (n) => n.id !== id && n.type === 'imageCard'
  ).length;

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    removeNode(id);
  };

  return (
    <div
      className={`relative rounded-3xl transition-all duration-200 pointer-events-none ${
        selected
          ? 'border-2 border-indigo-500 bg-indigo-950/15 shadow-2xl shadow-indigo-950/40 ring-4 ring-indigo-500/10'
          : 'border-2 border-dashed border-indigo-500/30 bg-slate-900/30 hover:border-indigo-500/50 hover:bg-slate-900/40'
      }`}
      style={{
        width,
        height,
      }}
    >
      {/* Frame Header Bar */}
      <div className="absolute -top-10 left-0 right-0 flex items-center justify-between px-3 py-1.5 pointer-events-auto">
        <div className="flex items-center gap-2 bg-slate-900/90 backdrop-blur-md px-3 py-1.5 rounded-xl border border-indigo-500/30 text-xs shadow-lg">
          <Layers className="w-3.5 h-3.5 text-indigo-400" />
          <span className="font-semibold text-slate-100">{frameData.label || 'Agent Workspace'}</span>
          <span className="text-[10px] bg-indigo-500/20 text-indigo-300 px-1.5 py-0.5 rounded-full font-mono">
            {containedCount} items
          </span>
        </div>

        <div className="flex items-center gap-1.5 bg-slate-900/90 backdrop-blur-md px-2 py-1 rounded-xl border border-slate-800 text-xs shadow-lg">
          <button
            onClick={handleRemove}
            className="p-1 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition"
            title="Delete Workspace Frame"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Frame Watermark / Guidance */}
      <div className="absolute inset-0 flex items-center justify-center opacity-15 pointer-events-none select-none">
        <div className="flex items-center gap-2 text-indigo-300 font-medium text-sm tracking-wider uppercase">
          <Sparkles className="w-5 h-5" />
          <span>Workspace Scratchpad</span>
        </div>
      </div>
    </div>
  );
});
