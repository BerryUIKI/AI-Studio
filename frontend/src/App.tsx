import { useEffect, useRef, useState } from 'react';
import {
  Activity,
  Cpu,
  Sparkles,
  Play,
  Trash2,
  Power,
  Upload,
  ExternalLink,
  Layers,
  Cloud,
  Server,
} from 'lucide-react';
import { NodePalette } from './components/canvas/NodePalette';
import { FlowCanvas } from './components/canvas/FlowCanvas';
import { CreationDock } from './components/canvas/CreationDock';
import { InpaintModal } from './components/canvas/InpaintModal';
import { UpscaleModal } from './components/canvas/UpscaleModal';
import { VideoModal } from './components/canvas/VideoModal';
import { AgentPanel } from './components/agent/AgentPanel';
import { CloudSettingsModal } from './components/cloud/CloudSettingsModal';
import { EnvironmentManagerModal } from './components/manager/EnvironmentManagerModal';
import { useCanvasStore } from './stores/useCanvasStore';
import { useCreativeStore } from './stores/useCreativeStore';

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
  const [showNodePalette, setShowNodePalette] = useState<boolean>(false);
  const [showCloudModal, setShowCloudModal] = useState<boolean>(false);
  const [showManagerModal, setShowManagerModal] = useState<boolean>(false);
  const [showAgentPanel, setShowAgentPanel] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const { nodes, clearCanvas, runWorkflow, isExecuting } = useCanvasStore();
  const { uploadCanvasImage } = useCreativeStore();

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
    const handleHash = () => {
      if (window.location.hash === '#manager' || window.location.search.includes('view=manager')) {
        setShowManagerModal(true);
      }
    };
    handleHash();
    window.addEventListener('hashchange', handleHash);

    const interval = setInterval(refreshStatus, 8000);
    return () => {
      window.removeEventListener('hashchange', handleHash);
      clearInterval(interval);
    };
  }, []);

  const toggleRuntime = async () => {
    if (runtimeStatus?.running) {
      await fetch('/api/v1/runtime/stop', { method: 'POST' });
    } else {
      await fetch('/api/v1/runtime/start', { method: 'POST' });
    }
    refreshStatus();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      uploadCanvasImage(file);
      e.target.value = '';
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 text-slate-100 select-none overflow-hidden">
      {/* Hidden File Input for Image Import */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept="image/*"
        className="hidden"
      />

      {/* Top Header Bar */}
      <header className="h-14 border-b border-slate-800 bg-slate-900/85 backdrop-blur px-4 flex items-center justify-between z-20">
        <div className="flex items-center gap-3">
          <div className="p-1.5 rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-semibold text-sm tracking-wide">Berry AI Studio</h1>
            <p className="text-[11px] text-slate-400">Creative Workspace & Infinite Canvas</p>
          </div>
        </div>

        {/* Action Controls: Import, Run Workflow, Clear */}
        <div className="flex items-center gap-2">
          {/* Import Image Button */}
          <button
            onClick={() => fileInputRef.current?.click()}
            title="Import an image directly onto the canvas"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition"
          >
            <Upload className="w-3.5 h-3.5 text-indigo-400" />
            <span>Import Image</span>
          </button>

          {/* Cloud BYOK Settings Button */}
          <button
            onClick={() => setShowCloudModal(true)}
            title="Configure BYOK Cloud Providers (OpenAI, Fal.ai, SiliconFlow)"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition"
          >
            <Cloud className="w-3.5 h-3.5 text-sky-400" />
            <span>Cloud BYOK</span>
          </button>

          {/* Environment Manager Button */}
          <button
            onClick={() => setShowManagerModal(true)}
            title="Open Environment Manager (Engines, Models, Updates, Core)"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition"
          >
            <Server className="w-3.5 h-3.5 text-purple-400" />
            <span>Environment</span>
          </button>

          {/* Conversational Agent Assistant Button */}
          <button
            onClick={() => setShowAgentPanel(!showAgentPanel)}
            title="Conversational AI Assistant (Natural Language Workflows & Human-in-the-Loop)"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition ${
              showAgentPanel
                ? 'bg-indigo-600/30 text-indigo-300 border-indigo-500/50 shadow-sm shadow-indigo-500/20'
                : 'bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>Agent</span>
          </button>

          {/* Toggle Node Palette for Power Users */}
          <button
            onClick={() => setShowNodePalette(!showNodePalette)}
            title="Toggle Node Palette"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition ${
              showNodePalette
                ? 'bg-indigo-600/20 text-indigo-300 border-indigo-500/40'
                : 'bg-slate-800 hover:bg-slate-700 text-slate-400 border-slate-700'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Nodes</span>
          </button>

          {/* Legacy/Power Workflow Runner */}
          {showNodePalette && (
            <button
              onClick={() => runWorkflow()}
              disabled={nodes.length === 0 || isExecuting}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-medium shadow-lg shadow-indigo-600/20 transition"
            >
              <Play className={`w-3.5 h-3.5 fill-current ${isExecuting ? 'animate-pulse' : ''}`} />
              {isExecuting ? 'Running...' : 'Run Graph'}
            </button>
          )}

          {/* Clear Canvas */}
          <button
            onClick={clearCanvas}
            disabled={nodes.length === 0 || isExecuting}
            title="Clear all objects from canvas"
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed text-slate-300 hover:text-rose-400 border border-slate-700 transition"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Engine Status Indicators & Native UI Entry Points */}
        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700">
            <Activity className={`w-3.5 h-3.5 ${backendOnline ? 'text-emerald-400' : 'text-rose-400 animate-pulse'}`} />
            <span className="text-slate-300">Backend: {backendOnline ? 'Online' : 'Connecting...'}</span>
          </div>

          {/* ComfyUI Indicator with Native Link */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700">
            <Cpu className={`w-3.5 h-3.5 ${comfyStatus?.online ? 'text-emerald-400' : 'text-slate-400'}`} />
            <span className="text-slate-300">
              ComfyUI: {comfyStatus?.online ? 'Online' : 'Standby'}
            </span>
            {comfyStatus?.online && (
              <a
                href="http://127.0.0.1:8188"
                target="_blank"
                rel="noreferrer"
                title="Open ComfyUI native web interface in a new tab"
                className="p-0.5 rounded text-slate-400 hover:text-indigo-400 transition"
              >
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
            {runtimeStatus?.installed && (
              <button
                onClick={toggleRuntime}
                title={runtimeStatus.running ? 'Stop isolated engine' : 'Start isolated engine'}
                className="p-0.5 rounded hover:bg-slate-700 text-slate-400 hover:text-indigo-400 transition"
              >
                <Power className={`w-3 h-3 ${runtimeStatus.running ? 'text-emerald-400' : 'text-slate-400'}`} />
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Workspace Layout */}
      <div className="flex-1 flex overflow-hidden relative">
        {showNodePalette && <NodePalette />}
        <main className="flex-1 relative">
          <FlowCanvas />
          {/* Newcomer Creative Creation Dock */}
          <CreationDock />
        </main>
      </div>

      {/* Contextual Action Modals */}
      <InpaintModal />
      <UpscaleModal />
      <VideoModal />
      <CloudSettingsModal isOpen={showCloudModal} onClose={() => setShowCloudModal(false)} />
      <EnvironmentManagerModal isOpen={showManagerModal} onClose={() => setShowManagerModal(false)} />
      <AgentPanel isOpen={showAgentPanel} onClose={() => setShowAgentPanel(false)} />
    </div>
  );
}
