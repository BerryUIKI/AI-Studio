import React, { useState, useEffect } from 'react';
import {
  X,
  FolderOpen,
  Download,
  CheckCircle2,
  AlertCircle,
  Puzzle,
  Image as ImageIcon,
  RefreshCw,
  Plus,
} from 'lucide-react';
import { useEngineStore } from '../../stores/useEngineStore';

interface AddEngineModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStartDeployment?: (engineType: 'comfyui' | 'webui', mirrorPreset: string) => void;
}

interface DetectedItem {
  engine_type: string;
  path: string;
  version?: string;
  has_python_env: boolean;
  python_executable?: string;
  recommended_name: string;
}

export const AddEngineModal: React.FC<AddEngineModalProps> = ({
  isOpen,
  onClose,
  onStartDeployment,
}) => {
  const [activeTab, setActiveTab] = useState<'detected' | 'browse' | 'install'>('detected');
  const [detectedList, setDetectedList] = useState<DetectedItem[]>([]);
  const [isScanning, setIsScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);

  // Manual browse form state
  const [manualType, setManualType] = useState<'comfyui' | 'webui'>('comfyui');
  const [manualName, setManualName] = useState('');
  const [manualPath, setManualPath] = useState('');
  const [manualPort, setManualPort] = useState<number>(8188);
  const [isSubmittingManual, setIsSubmittingManual] = useState(false);
  const [manualError, setManualError] = useState<string | null>(null);

  // Managed install state
  const [installEngineType, setInstallEngineType] = useState<'comfyui' | 'webui'>('comfyui');
  const [selectedMirror, setSelectedMirror] = useState<string>('china_mainland');

  const { fetchInstances } = useEngineStore();

  const scanForEngines = async () => {
    setIsScanning(true);
    setScanError(null);
    try {
      const res = await fetch('/api/v1/engines/detect');
      if (res.ok) {
        const data = await res.json();
        setDetectedList(data.detected || []);
      } else {
        setScanError('Failed to scan for local installations.');
      }
    } catch {
      setScanError('Unable to reach backend detection service.');
    } finally {
      setIsScanning(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      scanForEngines();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleBindDetected = async (item: DetectedItem) => {
    try {
      const res = await fetch('/api/v1/engines/bind', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          engine_type: item.engine_type,
          name: item.recommended_name,
          path: item.path,
          port: item.engine_type === 'comfyui' ? 8188 : 7860,
        }),
      });

      if (res.ok) {
        await fetchInstances();
        onClose();
      } else {
        const err = await res.json();
        alert(`Failed to bind: ${err.detail || 'Unknown error'}`);
      }
    } catch (e: any) {
      alert(`Network error: ${e.message}`);
    }
  };

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualPath.trim()) {
      setManualError('Please specify an installation directory path.');
      return;
    }

    setIsSubmittingManual(true);
    setManualError(null);
    try {
      const res = await fetch('/api/v1/engines/bind', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          engine_type: manualType,
          name: manualName || (manualType === 'comfyui' ? 'Custom ComfyUI' : 'Custom SD WebUI'),
          path: manualPath.trim(),
          port: manualPort,
        }),
      });

      if (res.ok) {
        await fetchInstances();
        onClose();
      } else {
        const err = await res.json();
        setManualError(err.detail || 'Directory validation failed.');
      }
    } catch (err: any) {
      setManualError(err.message || 'Connection error.');
    } finally {
      setIsSubmittingManual(false);
    }
  };

  const handleStartInstall = () => {
    if (onStartDeployment) {
      onStartDeployment(installEngineType, selectedMirror);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 select-none animate-in fade-in duration-150">
      <div className="relative w-full max-w-2xl rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl text-slate-100 overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center space-x-2">
            <Plus className="w-5 h-5 text-indigo-400" />
            <h2 className="text-base font-bold text-white">Add Engine Instance</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-800 bg-slate-900/80 px-6">
          <button
            onClick={() => setActiveTab('detected')}
            className={`py-3 px-4 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === 'detected'
                ? 'border-indigo-500 text-white'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Auto-Detected ({detectedList.length})
          </button>
          <button
            onClick={() => setActiveTab('browse')}
            className={`py-3 px-4 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === 'browse'
                ? 'border-indigo-500 text-white'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Browse Local Folder
          </button>
          <button
            onClick={() => setActiveTab('install')}
            className={`py-3 px-4 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === 'install'
                ? 'border-indigo-500 text-white'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            One-Click Install
          </button>
        </div>

        {/* Tab Contents */}
        <div className="p-6 overflow-y-auto flex-1">
          {activeTab === 'detected' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-xs text-slate-400">
                  Scanned your local disk for common ComfyUI, WebUI, and portable packages.
                </p>
                <button
                  onClick={scanForEngines}
                  disabled={isScanning}
                  className="inline-flex items-center space-x-1 px-2.5 py-1 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded transition-colors"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
                  <span>Rescan</span>
                </button>
              </div>

              {scanError && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400 flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{scanError}</span>
                </div>
              )}

              {detectedList.length === 0 && !isScanning ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <FolderOpen className="w-10 h-10 text-slate-600 mb-3" />
                  <p className="text-sm font-semibold text-slate-300">No external engines detected</p>
                  <p className="text-xs text-slate-500 mt-1 max-w-sm">
                    No installations were found in standard directories. You can specify a custom path in the "Browse Local Folder" tab, or deploy a new sandboxed engine.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {detectedList.map((item, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-4 rounded-xl bg-slate-800/50 border border-slate-700/60 hover:border-indigo-500/40 transition-colors"
                    >
                      <div className="flex items-start space-x-3">
                        <div className="w-9 h-9 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-indigo-400 mt-0.5">
                          {item.engine_type === 'comfyui' ? (
                            <Puzzle className="w-5 h-5" />
                          ) : (
                            <ImageIcon className="w-5 h-5" />
                          )}
                        </div>
                        <div>
                          <h4 className="text-xs font-bold text-slate-100">{item.recommended_name}</h4>
                          <p className="text-[11px] font-mono text-slate-400 break-all">{item.path}</p>
                          <div className="flex items-center space-x-2 mt-1">
                            <span className="inline-flex items-center text-[10px] text-emerald-400">
                              <CheckCircle2 className="w-3 h-3 mr-1" />
                              {item.has_python_env ? 'Isolated venv detected' : 'Standard environment'}
                            </span>
                          </div>
                        </div>
                      </div>

                      <button
                        onClick={() => handleBindDetected(item)}
                        className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-xs font-medium text-white rounded-lg transition-colors ml-4 whitespace-nowrap"
                      >
                        Bind Engine
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'browse' && (
            <form onSubmit={handleManualSubmit} className="space-y-4">
              <p className="text-xs text-slate-400">
                Specify the absolute root folder of an existing ComfyUI or SD WebUI installation.
              </p>

              {manualError && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400 flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{manualError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Engine Type</label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setManualType('comfyui');
                      setManualPort(8188);
                    }}
                    className={`flex items-center justify-center space-x-2 p-3 rounded-xl border text-xs font-medium transition-all ${
                      manualType === 'comfyui'
                        ? 'bg-indigo-600/10 border-indigo-500 text-indigo-300'
                        : 'bg-slate-800/40 border-slate-700 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <Puzzle className="w-4 h-4" />
                    <span>ComfyUI</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setManualType('webui');
                      setManualPort(7860);
                    }}
                    className={`flex items-center justify-center space-x-2 p-3 rounded-xl border text-xs font-medium transition-all ${
                      manualType === 'webui'
                        ? 'bg-indigo-600/10 border-indigo-500 text-indigo-300'
                        : 'bg-slate-800/40 border-slate-700 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <ImageIcon className="w-4 h-4" />
                    <span>SD WebUI</span>
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Directory Path</label>
                <input
                  type="text"
                  value={manualPath}
                  onChange={(e) => setManualPath(e.target.value)}
                  placeholder="e.g. D:\ComfyUI_windows_portable\ComfyUI"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Display Name (Optional)</label>
                  <input
                    type="text"
                    value={manualName}
                    onChange={(e) => setManualName(e.target.value)}
                    placeholder="My Custom Engine"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Port</label>
                  <input
                    type="number"
                    value={manualPort}
                    onChange={(e) => setManualPort(parseInt(e.target.value) || 8188)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  type="submit"
                  disabled={isSubmittingManual}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white rounded-lg transition-colors disabled:opacity-50"
                >
                  {isSubmittingManual ? 'Validating...' : 'Bind Directory'}
                </button>
              </div>
            </form>
          )}

          {activeTab === 'install' && (
            <div className="space-y-4">
              <p className="text-xs text-slate-400">
                Install a sandboxed, isolated engine environment with zero host system pollution.
              </p>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Target Engine</label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setInstallEngineType('comfyui')}
                    className={`flex items-center justify-center space-x-2 p-3 rounded-xl border text-xs font-medium transition-all ${
                      installEngineType === 'comfyui'
                        ? 'bg-indigo-600/10 border-indigo-500 text-indigo-300'
                        : 'bg-slate-800/40 border-slate-700 text-slate-400'
                    }`}
                  >
                    <Puzzle className="w-4 h-4" />
                    <span>ComfyUI (Recommended)</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setInstallEngineType('webui')}
                    className={`flex items-center justify-center space-x-2 p-3 rounded-xl border text-xs font-medium transition-all ${
                      installEngineType === 'webui'
                        ? 'bg-indigo-600/10 border-indigo-500 text-indigo-300'
                        : 'bg-slate-800/40 border-slate-700 text-slate-400'
                    }`}
                  >
                    <ImageIcon className="w-4 h-4" />
                    <span>SD WebUI</span>
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Network Acceleration Mirror
                </label>
                <div className="space-y-2">
                  <label className="flex items-center p-3 rounded-xl bg-slate-800/40 border border-slate-700 cursor-pointer hover:border-slate-600">
                    <input
                      type="radio"
                      name="mirror"
                      value="china_mainland"
                      checked={selectedMirror === 'china_mainland'}
                      onChange={(e) => setSelectedMirror(e.target.value)}
                      className="text-indigo-600 focus:ring-indigo-500 h-4 w-4 bg-slate-900 border-slate-700"
                    />
                    <div className="ml-3">
                      <div className="text-xs font-semibold text-slate-200">
                        China Mainland Accelerated (Recommended for CN users)
                      </div>
                      <div className="text-[11px] text-slate-400">
                        Uses GHProxy, Tsinghua pip mirror, and HF-Mirror for fast downloads.
                      </div>
                    </div>
                  </label>

                  <label className="flex items-center p-3 rounded-xl bg-slate-800/40 border border-slate-700 cursor-pointer hover:border-slate-600">
                    <input
                      type="radio"
                      name="mirror"
                      value="direct"
                      checked={selectedMirror === 'direct'}
                      onChange={(e) => setSelectedMirror(e.target.value)}
                      className="text-indigo-600 focus:ring-indigo-500 h-4 w-4 bg-slate-900 border-slate-700"
                    />
                    <div className="ml-3">
                      <div className="text-xs font-semibold text-slate-200">
                        Direct Official Sources
                      </div>
                      <div className="text-[11px] text-slate-400">
                        Direct connection to GitHub, PyPI.org, and HuggingFace.
                      </div>
                    </div>
                  </label>
                </div>
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  type="button"
                  onClick={handleStartInstall}
                  className="inline-flex items-center space-x-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white rounded-lg shadow-lg shadow-indigo-600/20 transition-all"
                >
                  <Download className="w-4 h-4" />
                  <span>Start Managed Installation</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
