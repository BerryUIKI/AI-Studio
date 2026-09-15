import { useEffect, useState } from 'react';
import { Activity, Cpu, Sparkles, Play, Trash2, Power } from 'lucide-react';
import { NodePalette } from './components/canvas/NodePalette';
import { FlowCanvas } from './components/canvas/FlowCanvas';
import { useCanvasStore } from './stores/useCanvasStore';

interface ComfyStatus {
  online: boolean;
  port: number;
  devices?: { name: string }[];
}

interface RuntimeStatus {
  installed: boolean;
  running: boolean;
  pid?: number;
}

export default function App() {
  const [backendOnline, setBackendOnline] = useState<boolean>(false);
  const [comfyStatus, setComfyStatus] = useState<ComfyStatus | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus | null>(null);
  const { nodes, clearCanvas, runWorkflow, isExecuting } = useCanvasStore();

  const refreshStatus = () => {
    fetch('/health')
      .then((res) => setBackendOnline(res.ok))
      .catch(() => setBackendOnline(false));

    fetch('/api/v1/comfy/status')
      .then((res) => res.json())
      .then((data) => setComfyStatus(data))
      .catch(() => {});

    fetch('/api/v1/runtime/status')
      .then((res) => res.json())
      .then((data) => setRuntimeStatus(data))
      .catch(() => {});
  };

  useEffect(() => {
    refreshStatus();
    const interval = setInterval(refreshStatus, 8000);
    return () => clearInterval(interval);
  }, []);

  const toggleRuntime = async () => {
    if (runtimeStatus?.running) {
      await fetch('/api/v1/runtime/stop', { method: 'POST' });
    } else {
      await fetch('/api/v1/runtime/start', { method: 'POST' });
    }
    refreshStatus();
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 text-slate-100 select-none">
      {/* Top Header Bar */}
      <header className="h-14 border-b border-slate-800 bg-slate-900/80 backdrop-blur px-4 flex items-center justify-between z-20">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-semibold text-sm tracking-wide">AI-Workflow</h1>
            <p className="text-[11px] text-slate-400">Multi-Modal Creative Canvas</p>
          </div>
        </div>

        {/* Global Workflow Action Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => runWorkflow()}
            disabled={nodes.length === 0 || isExecuting}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-medium shadow-lg shadow-indigo-600/20 transition"
          >
            <Play className={`w-3.5 h-3.5 fill-current ${isExecuting ? 'animate-pulse' : ''}`} />
            {isExecuting ? 'Running...' : 'Run Workflow'}
          </button>
          <button
            onClick={clearCanvas}
            disabled={nodes.length === 0 || isExecuting}
            title="Clear canvas"
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed text-slate-300 hover:text-rose-400 border border-slate-700 transition"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Engine Status Indicators */}
        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700">
            <Activity className={`w-3.5 h-3.5 ${backendOnline ? 'text-emerald-400' : 'text-rose-400 animate-pulse'}`} />
            <span className="text-slate-300">Backend: {backendOnline ? 'Online' : 'Connecting...'}</span>
          </div>

          <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700">
            <Cpu className={`w-3.5 h-3.5 ${comfyStatus?.online ? 'text-emerald-400' : 'text-slate-400'}`} />
            <span className="text-slate-300">
              Local Comfy: {comfyStatus?.online ? 'Online (8188)' : 'Standby'}
            </span>
            {runtimeStatus?.installed && (
              <button
                onClick={toggleRuntime}
                title={runtimeStatus.running ? 'Stop isolated engine' : 'Start isolated engine'}
                className="ml-1 p-0.5 rounded hover:bg-slate-700 text-slate-400 hover:text-indigo-400 transition"
              >
                <Power className={`w-3 h-3 ${runtimeStatus.running ? 'text-emerald-400' : 'text-slate-400'}`} />
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Workspace Layout */}
      <div className="flex-1 flex overflow-hidden relative">
        <NodePalette />
        <main className="flex-1 relative">
          <FlowCanvas />
        </main>
      </div>
    </div>
  );
}
