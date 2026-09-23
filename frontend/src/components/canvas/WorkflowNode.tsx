import { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { Play, CheckCircle2, Clock, AlertCircle } from 'lucide-react';
import { CustomNodeData, DataType } from '../../types/workflow';
import { useCanvasStore } from '../../stores/useCanvasStore';

const TYPE_COLORS: Record<DataType, string> = {
  string: '#fbbf24', // Amber
  image: '#34d399',  // Emerald
  audio: '#c084fc',  // Purple
  video: '#f43f5e',  // Rose
  json: '#60a5fa',   // Blue
};

function WorkflowNodeComponent({ id, data, selected }: NodeProps) {
  const customData = data as CustomNodeData;
  const { definition, params, status, output } = customData;
  const updateNodeParam = useCanvasStore((state) => state.updateNodeParam);
  const runWorkflow = useCanvasStore((state) => state.runWorkflow);

  const getStatusBadge = () => {
    switch (status) {
      case 'running':
        return (
          <span className="flex items-center gap-1 text-[10px] text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded border border-blue-500/20">
            <Clock className="w-2.5 h-2.5 animate-spin" /> Running
          </span>
        );
      case 'cached':
        return (
          <span className="flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
            <CheckCircle2 className="w-2.5 h-2.5" /> Cached
          </span>
        );
      case 'completed':
        return (
          <span className="flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
            <CheckCircle2 className="w-2.5 h-2.5" /> Done
          </span>
        );
      case 'error':
        return (
          <span className="flex items-center gap-1 text-[10px] text-rose-400 bg-rose-500/10 px-1.5 py-0.5 rounded border border-rose-500/20">
            <AlertCircle className="w-2.5 h-2.5" /> Error
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div
      className={`min-w-[260px] max-w-[320px] rounded-xl bg-slate-900/95 border backdrop-blur-md shadow-2xl transition-all ${
        selected ? 'border-indigo-500 ring-2 ring-indigo-500/30' : 'border-slate-800 hover:border-slate-700'
      }`}
    >
      {/* Node Header */}
      <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-slate-800/80 bg-slate-800/40 rounded-t-xl">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-indigo-500" />
          <h3 className="text-xs font-semibold text-slate-200">{definition.title}</h3>
        </div>
        <div className="flex items-center gap-1.5">
          {getStatusBadge()}
          <button
            onClick={() => runWorkflow(id)}
            title="Run this node"
            className="p-1 rounded hover:bg-slate-700/60 text-slate-400 hover:text-indigo-400 transition"
          >
            <Play className="w-3 h-3 fill-current" />
          </button>
        </div>
      </div>

      {/* Ports Area */}
      <div className="relative py-2 px-3">
        {/* Input Handles */}
        <div className="space-y-2 mb-2">
          {definition.inputs.map((input) => (
            <div key={input.id} className="relative flex items-center gap-2">
              <Handle
                type="target"
                position={Position.Left}
                id={input.id}
                style={{
                  backgroundColor: TYPE_COLORS[input.type] || '#94a3b8',
                  width: '9px',
                  height: '9px',
                  left: '-17px',
                }}
              />
              <span className="text-[11px] font-medium text-slate-300">{input.name}</span>
              <span className="text-[9px] uppercase px-1 rounded bg-slate-800 text-slate-400 border border-slate-700/50 ml-auto">
                {input.type}
              </span>
            </div>
          ))}
        </div>

        {/* Inline Parameters */}
        {definition.parameters.length > 0 && (
          <div className="mt-2 pt-2 border-t border-slate-800/60 space-y-2">
            {definition.parameters.map((param) => (
              <div key={param.name} className="space-y-1">
                <label className="text-[10px] font-medium text-slate-400">{param.label}</label>
                {param.type === 'textarea' ? (
                  <textarea
                    rows={2}
                    value={params[param.name] ?? ''}
                    onChange={(e) => updateNodeParam(id, param.name, e.target.value)}
                    placeholder={param.description}
                    className="w-full text-xs bg-slate-950/80 border border-slate-800 rounded px-2 py-1 text-slate-200 focus:outline-none focus:border-indigo-500 resize-none"
                  />
                ) : param.type === 'select' ? (
                  <select
                    value={params[param.name] ?? param.default}
                    onChange={(e) => updateNodeParam(id, param.name, e.target.value)}
                    className="w-full text-xs bg-slate-950/80 border border-slate-800 rounded px-2 py-1 text-slate-200 focus:outline-none focus:border-indigo-500"
                  >
                    {param.options?.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type={param.type === 'number' ? 'number' : 'text'}
                    value={params[param.name] ?? ''}
                    onChange={(e) =>
                      updateNodeParam(
                        id,
                        param.name,
                        param.type === 'number' ? parseFloat(e.target.value) : e.target.value,
                      )
                    }
                    className="w-full text-xs bg-slate-950/80 border border-slate-800 rounded px-2 py-1 text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {/* Output Handles */}
        <div className="space-y-2 mt-2 pt-2 border-t border-slate-800/60">
          {definition.outputs.map((outputPort) => (
            <div key={outputPort.id} className="relative flex items-center justify-end gap-2">
              <span className="text-[9px] uppercase px-1 rounded bg-slate-800 text-slate-400 border border-slate-700/50">
                {outputPort.type}
              </span>
              <span className="text-[11px] font-medium text-slate-300">{outputPort.name}</span>
              <Handle
                type="source"
                position={Position.Right}
                id={outputPort.id}
                style={{
                  backgroundColor: TYPE_COLORS[outputPort.type] || '#94a3b8',
                  width: '9px',
                  height: '9px',
                  right: '-17px',
                }}
              />
            </div>
          ))}
        </div>

        {/* Output Previews (Images, Text) */}
        {output?.image && (
          <div className="mt-2 pt-2 border-t border-slate-800/60">
            <img
              src={output.image}
              alt="Node Output"
              className="w-full h-32 object-cover rounded-lg border border-slate-800 shadow-md"
            />
          </div>
        )}
        {output?.result && (
          <div className="mt-2 pt-2 border-t border-slate-800/60">
            <div className="text-[11px] text-slate-300 bg-slate-950/70 p-2 rounded border border-slate-800 max-h-24 overflow-y-auto whitespace-pre-wrap">
              {output.result}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export const WorkflowNode = memo(WorkflowNodeComponent);
