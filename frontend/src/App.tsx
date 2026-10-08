import { useEffect, useRef, useState, useCallback } from 'react';
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
import { AddEngineModal } from './components/launcher/AddEngineModal';
import { DeploymentDrawer } from './components/launcher/DeploymentDrawer';
import { EngineConfigModal } from './components/launcher/EngineConfigModal';
import { EngineLogViewer } from './components/launcher/EngineLogViewer';
import { EngineNotInstalledModal } from './components/launcher/EngineNotInstalledModal';
import { SetupWizardModal } from './components/launcher/SetupWizardModal';
import { ExitConfirmDialog, RunningEngineItem } from './components/launcher/ExitConfirmDialog';
import { EmbeddedEngineView } from './components/engine/EmbeddedEngineView';
import { ModelHubView } from './components/hub/ModelHubView';
import { FloatingDownloadWidget } from './components/hub/FloatingDownloadWidget';
import { DownloadManagerDrawer } from './components/hub/DownloadManagerDrawer';
import { SettingsView } from './components/settings/SettingsView';
import { ErrorBoundary } from './components/ui/ErrorBoundary';
import { ProjectManagerModal } from './components/project/ProjectManagerModal';
import { TaskHistory } from './components/project/TaskHistory';
import { useCanvasStore } from './stores/useCanvasStore';
import { useCreativeStore } from './stores/useCreativeStore';
import { useEngineStore, type EngineInstance } from './stores/useEngineStore';
import { useSettingsStore } from './stores/useSettingsStore';
import { useNavigationStore } from './stores/useNavigationStore';
import { useProjectStore } from './stores/useProjectStore';
import { isTauri } from '@tauri-apps/api/core';
import { getCurrentWindow } from '@tauri-apps/api/window';

export default function App() {
  const [backendOnline, setBackendOnline] = useState<boolean>(false);
  const [comfyStatus, setComfyStatus] = useState<ComfyStatus | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus | null>(null);
  const [showNodePalette, setShowNodePalette] = useState<boolean>(false);
  const [showCloudModal, setShowCloudModal] = useState<boolean>(false);
  const [showManagerModal, setShowManagerModal] = useState<boolean>(false);
  const [showAgentPanel, setShowAgentPanel] = useState<boolean>(false);
  const [isMaximized, setIsMaximized] = useState<boolean>(false);
  const [showAddEngineModal, setShowAddEngineModal] = useState<boolean>(false);
  const [addEngineInitialTab, setAddEngineInitialTab] = useState<'detected' | 'browse' | 'install'>('detected');
  const [showDeploymentDrawer, setShowDeploymentDrawer] = useState<boolean>(false);
  const [deploymentEngineType, setDeploymentEngineType] = useState<'comfyui' | 'webui'>('comfyui');
  const [selectedConfigInstance, setSelectedConfigInstance] = useState<EngineInstance | null>(null);
  const [selectedLogInstance, setSelectedLogInstance] = useState<EngineInstance | null>(null);
  const [notInstalledTarget, setNotInstalledTarget] = useState<EngineInstance | null>(null);
  const [notInstalledError, setNotInstalledError] = useState<string | null>(null);
  const [showExitDialog, setShowExitDialog] = useState<boolean>(false);
  const [showSetupWizard, setShowSetupWizard] = useState<boolean>(false);
  const [showProjectModal, setShowProjectModal] = useState<boolean>(false);

  const { instances, fetchInstances, saveEngineConfig } = useEngineStore();
  const { exitPolicy, setExitPolicy, defaultLandingView } = useSettingsStore();
  const { setActiveView } = useNavigationStore();
  const { initProject, flushPendingSave } = useProjectStore();

  // Initialize active/default durable project on startup
  useEffect(() => {
    initProject();
  }, [initProject]);

  // Flush pending project autosaves when the window/tab is closing
  useEffect(() => {
    const handleBeforeUnload = () => {
      flushPendingSave();
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [flushPendingSave]);

  // Apply default landing view on initial mount
  useEffect(() => {
    if (defaultLandingView === 'canvas') {
      setActiveView('canvas');
    }
  }, [defaultLandingView, setActiveView]);

  const handleStartDeployment = (type: 'comfyui' | 'webui') => {
    setDeploymentEngineType(type);
    setShowDeploymentDrawer(true);
  };

  const handlePromptDeployment = (instance: EngineInstance, error?: string) => {
    setNotInstalledTarget(instance);
    setNotInstalledError(error || null);
  };

  const handleLocateExisting = (type: 'comfyui' | 'webui') => {
    setDeploymentEngineType(type);
    setAddEngineInitialTab('browse');
    setShowAddEngineModal(true);
  };

  const handleUninstallEngine = async (instance: EngineInstance) => {
    if (!instance.is_managed) {
      await fetch(`/api/v1/engines/unbind/${instance.id}`, { method: 'DELETE' });
    } else {
      await fetch(`/api/v1/runtime/${instance.type}/stop`, { method: 'POST' }).catch(() => {});
    }
    fetchInstances();
  };

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

    const handleOpenWizard = () => setShowSetupWizard(true);
    window.addEventListener('open-setup-wizard', handleOpenWizard);

    const interval = setInterval(refreshStatus, 8000);
    return () => {
      window.removeEventListener('hashchange', handleHash);
      window.removeEventListener('open-setup-wizard', handleOpenWizard);
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

  // Compute active running managed engines for exit policy prompt
  const getRunningManagedEngines = useCallback((): RunningEngineItem[] => {
    const running: RunningEngineItem[] = [];
    for (const inst of instances) {
      if (
        inst.is_managed &&
        !inst.is_builtin &&
        (inst.status === 'running' || (inst.id === 'comfyui-managed' && runtimeStatus?.running))
      ) {
        running.push({ id: inst.id, name: inst.name });
      }
    }
    if (runtimeStatus?.running && !running.some((e) => e.id === 'comfyui-managed')) {
      running.push({ id: 'comfyui-managed', name: 'ComfyUI Engine' });
    }
    return running;
  }, [instances, runtimeStatus]);

  const [activeTasksCount, setActiveTasksCount] = useState<number>(0);

  const checkActiveTasks = async (): Promise<number> => {
    try {
      const res = await fetch('/api/v1/tasks/active');
      if (res.ok) {
        const data = await res.json();
        const count = data.active_tasks_count ?? 0;
        setActiveTasksCount(count);
        return count;
      }
    } catch {
      // Fallback: check canvas executing state
    }
    const count = isExecuting ? 1 : 0;
    setActiveTasksCount(count);
    return count;
  };

  const closeAppWindow = async (options?: {
    mode?: 'keep_running' | 'stop_owned';
    force?: boolean;
    stopManagedEngines?: boolean;
  }) => {
    try {
      await flushPendingSave();
    } catch (e) {
      console.warn('Failed to flush pending project save before close:', e);
    }

    const mode = options?.mode || 'stop_owned';
    const force = options?.force || false;
    const stopManagedEngines = options?.stopManagedEngines;

    try {
      const isDesktop = isTauri() || (typeof window !== 'undefined' && ('__TAURI_INTERNALS__' in window || '__TAURI__' in window));
      if (isDesktop) {
        const { invoke } = await import('@tauri-apps/api/core');
        try {
          const res = await invoke<{ success: boolean; refused: boolean; message: string }>('close_app', {
            payload: {
              mode,
              force,
              stop_managed_engines: stopManagedEngines,
            },
          });
          if (res && res.refused) {
            console.warn('Backend refused shutdown due to active tasks:', res.message);
            setShowExitDialog(true);
            return;
          }
          return;
        } catch (e) {
          console.warn('invoke close_app failed, falling back to window destroy:', e);
        }
        const appWindow = getCurrentWindow();
        try {
          await appWindow.destroy();
          return;
        } catch {
          await appWindow.close();
          return;
        }
      } else {
        window.close();
      }
    } catch (err) {
      console.error('Failed to close app window:', err);
      try {
        window.close();
      } catch {}
    }
  };

  const handleKeepRunning = (remember: boolean) => {
    if (remember) {
      setExitPolicy('keep_running');
    }
    setShowExitDialog(false);
    closeAppWindow({ mode: 'keep_running' });
  };

  const handleCloseAllAndExit = async (remember: boolean, force = true) => {
    if (remember) {
      setExitPolicy('close_all');
    }
    setShowExitDialog(false);
    try {
      await fetch('/api/v1/runtime/stop', { method: 'POST' }).catch(() => {});
    } finally {
      closeAppWindow({ mode: 'stop_owned', force, stopManagedEngines: true });
    }
  };

  const handleCloseRequested = useCallback(async () => {
    const running = getRunningManagedEngines();
    const tasks = await checkActiveTasks();

    if (running.length === 0 && tasks === 0) {
      closeAppWindow({ mode: 'stop_owned', force: false });
      return;
    }

    if (tasks > 0 || exitPolicy === 'prompt') {
      setShowExitDialog(true);
    } else if (exitPolicy === 'close_all') {
      handleCloseAllAndExit(false, false);
    } else {
      // keep_running
      handleKeepRunning(false);
    }
  }, [getRunningManagedEngines, exitPolicy, isExecuting]);

  // Hook into native Tauri window close button / Alt+F4
  useEffect(() => {
    let unlistenClose: (() => void) | undefined;
    if (isTauri()) {
      getCurrentWindow()
        .onCloseRequested(async (event) => {
          const running = getRunningManagedEngines();
          const tasks = await checkActiveTasks();
          if ((running.length > 0 || tasks > 0) && (exitPolicy === 'prompt' || tasks > 0)) {
            event.preventDefault();
            setShowExitDialog(true);
          } else if (exitPolicy === 'keep_running') {
            event.preventDefault();
            handleKeepRunning(false);
          } else if (exitPolicy === 'close_all') {
            event.preventDefault();
            handleCloseAllAndExit(false, false);
          }
        })
        .then((fn) => {
          unlistenClose = fn;
        })
        .catch(() => {});
    }
    return () => {
      if (unlistenClose) unlistenClose();
    };
  }, [getRunningManagedEngines, exitPolicy]);

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
        onOpenProjectManager={() => setShowProjectModal(true)}
        showAgentPanel={showAgentPanel}
        onToggleAgent={() => setShowAgentPanel(!showAgentPanel)}
        showNodePalette={showNodePalette}
        onToggleNodePalette={() => setShowNodePalette(!showNodePalette)}
        onRunWorkflow={runWorkflow}
        isExecuting={isExecuting}
        hasNodes={nodes.length > 0}
        onClearCanvas={clearCanvas}
        onMaximizeChange={setIsMaximized}
        onCloseRequested={handleCloseRequested}
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
                onOpenAddEngine={() => {
                  setAddEngineInitialTab('detected');
                  setShowAddEngineModal(true);
                }}
                onConfigureEngine={(inst) => setSelectedConfigInstance(inst)}
                onViewLogs={(inst) => setSelectedLogInstance(inst)}
                onUninstallEngine={handleUninstallEngine}
                onOpenAgent={() => setShowAgentPanel(true)}
                onDeployEngine={(inst) => handlePromptDeployment(inst)}
                onLaunchFailed={(inst, err) => handlePromptDeployment(inst, err)}
                onOpenSetupWizard={() => setShowSetupWizard(true)}
              />
            ),
            canvas: (
              <ErrorBoundary fallbackTitle="Canvas Rendering Error" onReset={clearCanvas}>
                <div className="flex-1 flex w-full h-full overflow-hidden relative">
                  {showNodePalette && <NodePalette />}
                  <main className="flex-1 relative w-full h-full">
                    <FlowCanvas />
                    <TaskHistory />
                    <CreationDock />
                  </main>
                </div>
              </ErrorBoundary>
            ),
            models: (
              <ErrorBoundary fallbackTitle="Model Hub Error">
                <ModelHubView />
              </ErrorBoundary>
            ),
            comfyui: (() => {
              const comfyInst = instances.find((i) => i.id === 'comfyui-managed' || i.type === 'comfyui');
              const dynamicPort = comfyStatus?.port || (comfyInst?.endpoint ? Number(new URL(comfyInst.endpoint).port) : 8188) || 8188;
              return (
                <ErrorBoundary fallbackTitle="ComfyUI View Error">
                  <EmbeddedEngineView
                    engineType="comfyui"
                    title="ComfyUI"
                    port={dynamicPort}
                    isRunning={Boolean(runtimeStatus?.running || comfyStatus?.online)}
                    isInstalled={Boolean(
                      instances.find((i) => i.id === 'comfyui-managed')?.status !== 'not_installed' &&
                      runtimeStatus?.installed !== false
                    )}
                    onStartEngine={toggleRuntime}
                    onDeployEngine={() => handleStartDeployment('comfyui')}
                    onOpenDirectory={() => setShowManagerModal(true)}
                  />
                </ErrorBoundary>
              );
            })(),
            webui: (() => {
              const webuiInst = instances.find((i) => i.id === 'webui-managed' || i.type === 'webui');
              const dynamicPort = (webuiInst?.endpoint ? Number(new URL(webuiInst.endpoint).port) : 7860) || 7860;
              return (
                <ErrorBoundary fallbackTitle="SD WebUI View Error">
                  <EmbeddedEngineView
                    engineType="webui"
                    title="SD WebUI"
                    port={dynamicPort}
                    isRunning={Boolean(instances.find((i) => i.id === 'webui-managed')?.status === 'running')}
                    isInstalled={Boolean(instances.find((i) => i.id === 'webui-managed')?.status !== 'not_installed')}
                    onStartEngine={toggleRuntime}
                    onDeployEngine={() => handleStartDeployment('webui')}
                    onOpenDirectory={() => setShowManagerModal(true)}
                  />
                </ErrorBoundary>
              );
            })(),
            settings: (
              <SettingsView
                onOpenCloudSettings={() => setShowCloudModal(true)}
                onOpenEnvironmentManager={() => setShowManagerModal(true)}
              />
            ),
          }}
        </ViewContainer>

        {/* Persistent Collapsible Right Sidebar AI Agent */}
        {showAgentPanel && (
          <aside className="w-96 flex-shrink-0 h-full border-l border-slate-800 bg-slate-900 shadow-2xl z-30 transition-all duration-200">
            <AgentPanel
              isOpen={showAgentPanel}
              onClose={() => setShowAgentPanel(false)}
              inline={true}
            />
          </aside>
        )}
      </div>

      {/* Contextual Action Modals */}
      <InpaintModal />
      <UpscaleModal />
      <VideoModal />
      <CloudSettingsModal isOpen={showCloudModal} onClose={() => setShowCloudModal(false)} />
      <EnvironmentManagerModal isOpen={showManagerModal} onClose={() => setShowManagerModal(false)} />
      <ProjectManagerModal isOpen={showProjectModal} onClose={() => setShowProjectModal(false)} />
      <AddEngineModal
        isOpen={showAddEngineModal}
        initialTab={addEngineInitialTab}
        initialEngineType={deploymentEngineType}
        onClose={() => setShowAddEngineModal(false)}
        onStartDeployment={handleStartDeployment}
      />
      <DeploymentDrawer
        isOpen={showDeploymentDrawer}
        engineType={deploymentEngineType}
        onClose={() => setShowDeploymentDrawer(false)}
      />
      <EngineNotInstalledModal
        isOpen={!!notInstalledTarget}
        instance={notInstalledTarget}
        errorMessage={notInstalledError}
        onClose={() => {
          setNotInstalledTarget(null);
          setNotInstalledError(null);
        }}
        onDeploy={(type) => handleStartDeployment(type)}
        onLocate={(type) => handleLocateExisting(type)}
      />
      <SetupWizardModal
        isOpen={showSetupWizard}
        onClose={() => setShowSetupWizard(false)}
        onNavigateToAgent={() => {
          setShowSetupWizard(false);
          setShowAgentPanel(true);
        }}
      />
      <EngineConfigModal
        isOpen={!!selectedConfigInstance}
        instance={
          selectedConfigInstance
            ? instances.find((i) => i.id === selectedConfigInstance.id) || selectedConfigInstance
            : null
        }
        onClose={() => setSelectedConfigInstance(null)}
        onSave={async (instanceId, config) => {
          return await saveEngineConfig(instanceId, config);
        }}
      />
      <EngineLogViewer
        isOpen={!!selectedLogInstance}
        instance={selectedLogInstance}
        onClose={() => setSelectedLogInstance(null)}
      />
      <ExitConfirmDialog
        isOpen={showExitDialog}
        runningEngines={getRunningManagedEngines()}
        activeTasksCount={activeTasksCount}
        onKeepRunning={handleKeepRunning}
        onCloseAllAndExit={handleCloseAllAndExit}
        onCancel={() => setShowExitDialog(false)}
      />

      {/* Model Hub Download Manager & Floating Widget (MH-M5) */}
      <FloatingDownloadWidget />
      <DownloadManagerDrawer />
    </div>
  );
}
