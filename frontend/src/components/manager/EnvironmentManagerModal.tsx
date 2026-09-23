import React, { useState, useEffect } from 'react';
import {
  X,
  Server,
  Cpu,
  RefreshCw,
  Power,
  Play,
  Square,
  Download,
  FolderPlus,
  Trash2,
  CheckCircle2,
} from 'lucide-react';

interface EngineConn {
  id: string;
  name: string;
  engine_type: string;
  ownership: string;
  endpoint_url: string;
  status: string;
  native_ui_url?: string;
  version?: string;
  vram_free_mb?: number;
  capabilities: string[];
  error_message?: string;
}

interface ManagerStatus {
  app_name: string;
  version: string;
  pid: number;
  uptime_seconds: number;
  port: number;
  frontend_packaged: boolean;
  managed_comfyui: EngineConn;
  managed_webui: EngineConn;
  external_engines: EngineConn[];
  cloud_providers_configured: number;
  models_indexed: number;
  active_tasks: number;
  launcher_config: {
    stop_managed_engines_on_exit: boolean;
    default_engine: string;
  };
}

interface ModelItem {
  id: string;
  name: string;
  file_path: string;
  category: string;
  architecture: string;
  size_mb: number;
  engine_compatibility: string[];
  is_ready: boolean;
  missing_dependencies: string[];
  guidance?: string;
}

interface ModelRoot {
  id: string;
  path: string;
  label: string;
  engine_type?: string;
  exists: boolean;
  models_found: number;
}

interface EnvironmentManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const EnvironmentManagerModal: React.FC<EnvironmentManagerModalProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'engines' | 'models' | 'updates'>('overview');
  const [status, setStatus] = useState<ManagerStatus | null>(null);
  const [models, setModels] = useState<ModelItem[]>([]);
  const [roots, setRoots] = useState<ModelRoot[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [rescanning, setRescanning] = useState<boolean>(false);
  const [newRootPath, setNewRootPath] = useState<string>('');
  const [newRootLabel, setNewRootLabel] = useState<string>('');
  const [shuttingDown, setShuttingDown] = useState<boolean>(false);
  const [shutdownError, setShutdownError] = useState<string | null>(null);
  const [updateManifest, setUpdateManifest] = useState<any>(null);

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/v1/manager/status');
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (err) {
      console.error('Failed to fetch manager status:', err);
    }
  };

  const fetchModels = async () => {
    try {
      const [mRes, rRes] = await Promise.all([
        fetch('/api/v1/models'),
        fetch('/api/v1/models/roots'),
      ]);
      if (mRes.ok) setModels(await mRes.json());
      if (rRes.ok) setRoots(await rRes.json());
    } catch (err) {
      console.error('Failed to fetch models:', err);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchStatus();
      fetchModels();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleStartEngine = async (type: string) => {
    setLoading(true);
    await fetch(`/api/v1/runtime/${type === 'webui' ? 'webui/' : ''}start`, { method: 'POST' });
    await fetchStatus();
    setLoading(false);
  };

  const handleStopEngine = async (type: string) => {
    setLoading(true);
    await fetch(`/api/v1/runtime/${type === 'webui' ? 'webui/' : ''}stop`, { method: 'POST' });
    await fetchStatus();
    setLoading(false);
  };

  const handleInstallEngine = async (type: string) => {
    setLoading(true);
    await fetch(`/api/v1/runtime/${type}/install`, { method: 'POST' });
    await fetchStatus();
    setLoading(false);
  };

  const handleUpdateEngine = async (type: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/runtime/${type}/update`, { method: 'POST' });
      if (res.ok) {
        const manifest = await res.json();
        setUpdateManifest(manifest);
      }
    } catch (err) {
      console.error('Update failed:', err);
    }
    await fetchStatus();
    setLoading(false);
  };

  const handleRescanModels = async () => {
    setRescanning(true);
    try {
      const res = await fetch('/api/v1/models/rescan', { method: 'POST' });
      if (res.ok) setModels(await res.json());
      await fetchStatus();
    } finally {
      setRescanning(false);
    }
  };

  const handleAddRoot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRootPath || !newRootLabel) return;
    try {
      const res = await fetch('/api/v1/models/roots', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: newRootPath, label: newRootLabel }),
      });
      if (res.ok) {
        setNewRootPath('');
        setNewRootLabel('');
        fetchModels();
      }
    } catch (err) {
      console.error('Failed to add root:', err);
    }
  };

  const handleRemoveRoot = async (id: string) => {
    try {
      await fetch(`/api/v1/models/roots/${id}`, { method: 'DELETE' });
      fetchModels();
    } catch (err) {
      console.error('Failed to remove root:', err);
    }
  };

  const handleShutdown = async (force = false) => {
    setShuttingDown(true);
    setShutdownError(null);
    try {
      const res = await fetch('/api/v1/manager/shutdown', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force }),
      });
      if (res.ok) {
        setTimeout(() => window.close(), 1000);
      } else if (res.status === 409) {
        const err = await res.json();
        setShutdownError(err.detail || 'Active tasks running. Confirm force exit?');
      }
    } catch (err) {
      setShutdownError('Server disconnected or shutdown failed.');
    } finally {
      setShuttingDown(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="flex flex-col w-full max-w-4xl h-[85vh] bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-purple-500/20 text-purple-400">
              <Server className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Environment Manager</h2>
              <p className="text-xs text-slate-400">Manage Berry core, engines, model inventory, and updates</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-2 px-6 py-2 border-b border-slate-800 bg-slate-900/50">
          <button
            onClick={() => setActiveTab('overview')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeTab === 'overview' ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Core & Overview
          </button>
          <button
            onClick={() => setActiveTab('engines')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeTab === 'engines' ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Engines Lifecycle
          </button>
          <button
            onClick={() => setActiveTab('models')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeTab === 'models' ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Model Inventory ({models.length})
          </button>
          <button
            onClick={() => setActiveTab('updates')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeTab === 'updates' ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Updates & Recovery
          </button>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Tab: Overview */}
          {activeTab === 'overview' && status && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60">
                  <div className="text-xs text-slate-400 font-medium">Berry AI Studio Core</div>
                  <div className="text-xl font-bold text-white mt-1">v{status.version}</div>
                  <div className="text-xs text-emerald-400 mt-1 flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> PID: {status.pid} • Port: {status.port}
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60">
                  <div className="text-xs text-slate-400 font-medium">Active Tasks</div>
                  <div className="text-xl font-bold text-white mt-1">{status.active_tasks}</div>
                  <div className="text-xs text-slate-400 mt-1">
                    Uptime: {Math.floor(status.uptime_seconds / 60)}m {Math.floor(status.uptime_seconds % 60)}s
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60">
                  <div className="text-xs text-slate-400 font-medium">Cloud & Models</div>
                  <div className="text-xl font-bold text-white mt-1">{status.models_indexed} Models</div>
                  <div className="text-xs text-indigo-400 mt-1">
                    {status.cloud_providers_configured} Cloud Key(s) Configured
                  </div>
                </div>
              </div>

              {/* Shutdown Card */}
              <div className="p-5 rounded-xl bg-rose-950/20 border border-rose-900/40 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-rose-300">Exit Berry AI Studio</h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Terminates Berry application process safely. External user engines are never stopped.
                    </p>
                  </div>
                  <button
                    onClick={() => handleShutdown(false)}
                    disabled={shuttingDown}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold shadow transition disabled:opacity-50"
                  >
                    <Power className="w-4 h-4" />
                    Exit Berry
                  </button>
                </div>
                {shutdownError && (
                  <div className="p-3 rounded-lg bg-rose-900/50 border border-rose-700/60 text-xs text-rose-200 flex items-center justify-between">
                    <span>{shutdownError}</span>
                    <button
                      onClick={() => handleShutdown(true)}
                      className="px-2 py-1 rounded bg-rose-700 hover:bg-rose-600 text-white font-medium ml-3"
                    >
                      Force Exit
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tab: Engines */}
          {activeTab === 'engines' && status && (
            <div className="space-y-4">
              {/* Managed ComfyUI */}
              <div className="p-5 rounded-xl bg-slate-800/60 border border-slate-700/60 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-indigo-500/20 text-indigo-400">
                      <Cpu className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-white">{status.managed_comfyui.name}</h3>
                      <p className="text-xs text-slate-400">{status.managed_comfyui.endpoint_url}</p>
                    </div>
                  </div>
                  <span
                    className={`px-2.5 py-1 rounded-full text-xs font-semibold capitalize ${
                      status.managed_comfyui.status === 'running' || status.managed_comfyui.status === 'ready'
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : status.managed_comfyui.status === 'not_installed'
                        ? 'bg-amber-500/20 text-amber-300'
                        : 'bg-slate-700 text-slate-300'
                    }`}
                  >
                    {status.managed_comfyui.status}
                  </span>
                </div>

                <div className="flex items-center gap-2 pt-2">
                  {status.managed_comfyui.status === 'not_installed' ? (
                    <button
                      onClick={() => handleInstallEngine('comfyui')}
                      disabled={loading}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition"
                    >
                      <Download className="w-3.5 h-3.5" /> Install ComfyUI
                    </button>
                  ) : status.managed_comfyui.status === 'running' ? (
                    <button
                      onClick={() => handleStopEngine('comfyui')}
                      disabled={loading}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-medium transition"
                    >
                      <Square className="w-3.5 h-3.5" /> Stop
                    </button>
                  ) : (
                    <button
                      onClick={() => handleStartEngine('comfyui')}
                      disabled={loading}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition"
                    >
                      <Play className="w-3.5 h-3.5" /> Start
                    </button>
                  )}

                  <button
                    onClick={() => handleUpdateEngine('comfyui')}
                    disabled={loading || status.managed_comfyui.status === 'not_installed'}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-medium transition disabled:opacity-40"
                  >
                    <RefreshCw className="w-3.5 h-3.5" /> Update Engine
                  </button>
                </div>
              </div>

              {/* Managed WebUI */}
              <div className="p-5 rounded-xl bg-slate-800/60 border border-slate-700/60 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-purple-500/20 text-purple-400">
                      <Cpu className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-white">{status.managed_webui.name}</h3>
                      <p className="text-xs text-slate-400">{status.managed_webui.endpoint_url}</p>
                    </div>
                  </div>
                  <span
                    className={`px-2.5 py-1 rounded-full text-xs font-semibold capitalize ${
                      status.managed_webui.status === 'running' || status.managed_webui.status === 'ready'
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : status.managed_webui.status === 'not_installed'
                        ? 'bg-amber-500/20 text-amber-300'
                        : 'bg-slate-700 text-slate-300'
                    }`}
                  >
                    {status.managed_webui.status}
                  </span>
                </div>

                <div className="flex items-center gap-2 pt-2">
                  {status.managed_webui.status === 'not_installed' ? (
                    <button
                      onClick={() => handleInstallEngine('webui')}
                      disabled={loading}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium transition"
                    >
                      <Download className="w-3.5 h-3.5" /> Install SD WebUI
                    </button>
                  ) : status.managed_webui.status === 'running' ? (
                    <button
                      onClick={() => handleStopEngine('webui')}
                      disabled={loading}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-medium transition"
                    >
                      <Square className="w-3.5 h-3.5" /> Stop
                    </button>
                  ) : (
                    <button
                      onClick={() => handleStartEngine('webui')}
                      disabled={loading}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition"
                    >
                      <Play className="w-3.5 h-3.5" /> Start
                    </button>
                  )}

                  <button
                    onClick={() => handleUpdateEngine('webui')}
                    disabled={loading || status.managed_webui.status === 'not_installed'}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-medium transition disabled:opacity-40"
                  >
                    <RefreshCw className="w-3.5 h-3.5" /> Update Engine
                  </button>
                </div>
              </div>

              {/* External Engines */}
              <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 space-y-2">
                <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Connected External Engines (Zero Process Ownership)
                </h4>
                {status.external_engines.length === 0 ? (
                  <p className="text-xs text-slate-500">No external user engines currently connected.</p>
                ) : (
                  status.external_engines.map((ext) => (
                    <div key={ext.id} className="flex items-center justify-between text-xs p-2 rounded bg-slate-800/40">
                      <span className="text-white font-medium">{ext.name}</span>
                      <span className="text-slate-400">{ext.endpoint_url} [{ext.status}]</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* Tab: Models */}
          {activeTab === 'models' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-white">Unified Model Inventory</h3>
                  <p className="text-xs text-slate-400">Pure-Python safetensors inspection across registered directories</p>
                </div>
                <button
                  onClick={handleRescanModels}
                  disabled={rescanning}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium transition disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${rescanning ? 'animate-spin' : ''}`} />
                  Rescan Directories
                </button>
              </div>

              {/* Registered Roots */}
              <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50 space-y-3">
                <h4 className="text-xs font-semibold text-slate-300">Registered Model Scan Roots</h4>
                <div className="space-y-1.5">
                  {roots.map((r) => (
                    <div key={r.id} className="flex items-center justify-between text-xs p-2 rounded bg-slate-800/80">
                      <div>
                        <span className="font-medium text-white">{r.label}</span>
                        <span className="text-slate-400 ml-2">({r.path})</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-slate-400">{r.models_found} models</span>
                        {r.id.startsWith('root_') && (
                          <button
                            onClick={() => handleRemoveRoot(r.id)}
                            className="p-1 text-rose-400 hover:text-rose-300"
                            title="Remove Root"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Add Root Form */}
                <form onSubmit={handleAddRoot} className="flex items-center gap-2 pt-2 border-t border-slate-700/50">
                  <input
                    type="text"
                    placeholder="Directory Path (e.g. F:\models\checkpoints)"
                    value={newRootPath}
                    onChange={(e) => setNewRootPath(e.target.value)}
                    className="flex-1 px-3 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                  <input
                    type="text"
                    placeholder="Label (e.g. My SDXL Models)"
                    value={newRootLabel}
                    onChange={(e) => setNewRootLabel(e.target.value)}
                    className="w-44 px-3 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                  <button
                    type="submit"
                    className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium flex items-center gap-1"
                  >
                    <FolderPlus className="w-3.5 h-3.5" /> Add Root
                  </button>
                </form>
              </div>

              {/* Models Table */}
              <div className="overflow-x-auto border border-slate-800 rounded-xl">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950/80 text-slate-400 font-semibold border-b border-slate-800">
                    <tr>
                      <th className="px-3 py-2.5">Name</th>
                      <th className="px-3 py-2.5">Category</th>
                      <th className="px-3 py-2.5">Arch</th>
                      <th className="px-3 py-2.5">Size</th>
                      <th className="px-3 py-2.5">Compatibility</th>
                      <th className="px-3 py-2.5">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {models.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                          No models detected in registered directories. Add a custom root above to scan.
                        </td>
                      </tr>
                    ) : (
                      models.map((m) => (
                        <tr key={m.id} className="hover:bg-slate-800/40 transition">
                          <td className="px-3 py-2 font-medium text-white max-w-[200px] truncate" title={m.file_path}>
                            {m.name}
                          </td>
                          <td className="px-3 py-2 capitalize">{m.category}</td>
                          <td className="px-3 py-2 uppercase">{m.architecture}</td>
                          <td className="px-3 py-2">{m.size_mb} MB</td>
                          <td className="px-3 py-2">
                            <div className="flex gap-1">
                              {m.engine_compatibility.map((c) => (
                                <span key={c} className="px-1.5 py-0.5 rounded bg-slate-700 text-[10px] uppercase">
                                  {c}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="px-3 py-2">
                            {m.is_ready ? (
                              <span className="text-emerald-400">Ready</span>
                            ) : (
                              <span className="text-amber-400" title={m.guidance || ''}>
                                Missing Dependencies
                              </span>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Tab: Updates */}
          {activeTab === 'updates' && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50 space-y-2">
                <h3 className="text-sm font-semibold text-white">Berry AI Studio Application Updates</h3>
                <p className="text-xs text-slate-400">
                  Berry application updates are maintained separately from inference engine updates.
                </p>
                <div className="flex items-center gap-3 pt-2">
                  <span className="text-xs text-slate-300">Current Version: <strong className="text-white">v0.1.0</strong></span>
                  <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-xs font-medium">Up to Date</span>
                </div>
              </div>

              {updateManifest && (
                <div className="p-4 rounded-xl bg-indigo-950/30 border border-indigo-800/50 space-y-2">
                  <h4 className="text-xs font-semibold text-indigo-300 uppercase">Recent Engine Update Result</h4>
                  <div className="text-xs text-slate-300 space-y-1">
                    <div>Engine: <strong>{updateManifest.engine_type}</strong></div>
                    <div>Status: <strong>{updateManifest.status}</strong></div>
                    {updateManifest.previous_commit && <div>Previous Commit: <code>{updateManifest.previous_commit}</code></div>}
                    {updateManifest.rollback_performed && (
                      <div className="text-amber-300 font-semibold">Rollback performed successfully to previous working commit.</div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
