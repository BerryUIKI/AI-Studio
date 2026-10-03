import { useEffect, useRef, useState } from 'react';
import { Titlebar, type ComfyStatus, type RuntimeStatus } from './components/titlebar/Titlebar';
import { NodePalette } from './components/canvas/NodePalette';
import { FlowCanvas } from './components/canvas/FlowCanvas';
import { CreationDock } from './components/canvas/CreationDock';
import { InpaintModal } from './components/canvas/InpaintModal';
import { UpscaleModal } from './components/canvas/UpscaleModal';
import { VideoModal } from './components/canvas/VideoModal';
import { AgentPanel } from './components/agent/AgentPanel';
import { CloudSettingsModal } from './components/cloud/CloudSettingsModal';
import { EnvironmentManagerModal } from './components/manager/EnvironmentManagerModal';
import { GlobalNavRail } from './components/navigation/GlobalNavRail';
import { ViewContainer } from './components/navigation/ViewContainer';
import { LauncherHub } from './components/launcher/LauncherHub';
import { EmbeddedEngineView } from './components/engine/EmbeddedEngineView';
import { SettingsView } from './components/settings/SettingsView';
import { useCanvasStore } from './stores/useCanvasStore';
import { useCreativeStore } from './stores/useCreativeStore';

export default function App() {
  const [backendOnline, setBackendOnline] = useState<boolean>(false);
  const [comfyStatus, setComfyStatus] = useState<ComfyStatus | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus | null>(null);
  const [showNodePalette, setShowNodePalette] = useState<boolean>(false);
  const [showCloudModal, setShowCloudModal] = useState<boolean>(false);
  const [showManagerModal, setShowManagerModal] = useState<boolean>(false);
  const [showAgentPanel, setShowAgentPanel] = useState<boolean>(false);
  const [isMaximized, setIsMaximized] = useState<boolean>(false);

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
    <div
      className={`flex flex-col h-screen w-screen bg-slate-950 text-slate-100 select-none overflow-hidden transition-all duration-150 ${
        isMaximized ? 'rounded-none border-0' : 'rounded-lg border border-white/[0.08] shadow-2xl'
      }`}
    >
      {/* Hidden File Input for Image Import */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept="image/*"
        className="hidden"
      />

      {/* Modern Custom Frameless Titlebar */}
      <Titlebar
        backendOnline={backendOnline}
        comfyStatus={comfyStatus}
        runtimeStatus={runtimeStatus}
        toggleRuntime={toggleRuntime}
        onImportImage={() => fileInputRef.current?.click()}
        onOpenCloud={() => setShowCloudModal(true)}
        onOpenManager={() => setShowManagerModal(true)}
        showAgentPanel={showAgentPanel}
        onToggleAgent={() => setShowAgentPanel(!showAgentPanel)}
        showNodePalette={showNodePalette}
        onToggleNodePalette={() => setShowNodePalette(!showNodePalette)}
        onRunWorkflow={runWorkflow}
        isExecuting={isExecuting}
        hasNodes={nodes.length > 0}
        onClearCanvas={clearCanvas}
        onMaximizeChange={setIsMaximized}
      />

      {/* Main Workspace Layout with Global Navigation Rail and Keep-Alive View Container */}
      <div className="flex-1 flex overflow-hidden relative">
        <GlobalNavRail
          comfyOnline={comfyStatus?.online}
          comfyRunning={runtimeStatus?.running}
          webuiOnline={false}
          webuiRunning={false}
          isGenerating={isExecuting}
        />
        <ViewContainer>
          {{
            launcher: (
              <LauncherHub
                comfyOnline={comfyStatus?.online}
                comfyRunning={runtimeStatus?.running}
                webuiOnline={false}
                webuiRunning={false}
                onStartComfy={toggleRuntime}
                onStartWebui={toggleRuntime}
                onOpenAddEngine={() => setShowManagerModal(true)}
              />
            ),
            canvas: (
              <div className="flex-1 flex w-full h-full overflow-hidden relative">
                {showNodePalette && <NodePalette />}
                <main className="flex-1 relative w-full h-full">
                  <FlowCanvas />
                  <CreationDock />
                </main>
              </div>
            ),
            comfyui: (
              <EmbeddedEngineView
                engineType="comfyui"
                title="ComfyUI"
                port={comfyStatus?.port || 8188}
                isRunning={Boolean(runtimeStatus?.running || comfyStatus?.online)}
                onStartEngine={toggleRuntime}
                onOpenDirectory={() => setShowManagerModal(true)}
              />
            ),
            webui: (
              <EmbeddedEngineView
                engineType="webui"
                title="Stable Diffusion WebUI"
                port={7860}
                isRunning={false}
                onStartEngine={toggleRuntime}
                onOpenDirectory={() => setShowManagerModal(true)}
              />
            ),
            agents: (
              <div className="w-full h-full flex flex-col bg-slate-950 p-6 overflow-hidden">
                <AgentPanel isOpen={true} onClose={() => {}} inline={true} />
              </div>
            ),
            settings: (
              <SettingsView
                onOpenCloudSettings={() => setShowCloudModal(true)}
                onOpenEnvironmentManager={() => setShowManagerModal(true)}
              />
            ),
          }}
        </ViewContainer>
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
