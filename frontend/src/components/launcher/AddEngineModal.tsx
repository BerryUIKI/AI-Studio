import { useUiText } from '../../i18n/useUiText';
import { errorMessage as getErrorMessage } from '../../utils/errors';
import { Dialog } from '../ui/Dialog';
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
  initialTab?: 'detected' | 'browse' | 'install';
  initialEngineType?: 'comfyui' | 'webui';
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
  initialTab = 'detected',
  initialEngineType = 'comfyui',
}) => {
  const ui = useUiText();
  const [activeTab, setActiveTab] = useState<'detected' | 'browse' | 'install'>(initialTab);
  const [detectedList, setDetectedList] = useState<DetectedItem[]>([]);
  const [isScanning, setIsScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);

  // Manual browse form state
  const [manualType, setManualType] = useState<'comfyui' | 'webui'>(initialEngineType);
  const [manualName, setManualName] = useState('');
  const [manualPath, setManualPath] = useState('');
  const [manualPort, setManualPort] = useState<number>(8188);
  const [isSubmittingManual, setIsSubmittingManual] = useState(false);
  const [manualError, setManualError] = useState<string | null>(null);

  // Managed install state
  const [installEngineType, setInstallEngineType] = useState<'comfyui' | 'webui'>(initialEngineType);
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
        setScanError(ui("ui_failed_to_scan_for_local_installations"));
      }
    } catch {
      setScanError(ui("ui_unable_to_reach_backend_detection_service"));
    } finally {
      setIsScanning(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab);
      setManualType(initialEngineType);
      setInstallEngineType(initialEngineType);
      scanForEngines();
    }
  }, [isOpen, initialTab, initialEngineType]);

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
        alert(ui("ui_failed_to_bind_value", { value1: err.detail || 'Unknown error' }));
      }
    } catch (e: unknown) {
      alert(ui("ui_network_error_value", { value1: getErrorMessage(e, 'Unknown error') }));
    }
  };

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualPath.trim()) {
      setManualError(ui("ui_please_specify_an_installation_directory_path"));
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
        setManualError(err.detail || ui("ui_directory_validation_failed"));
      }
    } catch (err: unknown) {
      setManualError(getErrorMessage(err, ui("ui_connection_error")));
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
    <Dialog title={ui("ui_add_engine")} onClose={onClose} className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 select-none animate-in fade-in duration-150">
      <div className="relative w-full max-w-2xl rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl text-slate-100 overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center space-x-2">
            <Plus className="w-5 h-5 text-indigo-400" />
            <h2 className="text-base font-bold text-white">{ui("ui_add_engine_instance")}</h2>
          </div>
          <button
            onClick={onClose}
            aria-label={ui("ui_close_dialog")}
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
            {ui("ui_auto_detected")}{detectedList.length})
          </button>
          <button
            onClick={() => setActiveTab('browse')}
            className={`py-3 px-4 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === 'browse'
                ? 'border-indigo-500 text-white'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            {ui("ui_browse_local_folder")}</button>
          <button
            onClick={() => setActiveTab('install')}
            className={`py-3 px-4 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === 'install'
                ? 'border-indigo-500 text-white'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            {ui("ui_one_click_install")}</button>
        </div>

        {/* Tab Contents */}
        <div className="p-6 overflow-y-auto flex-1">
          {activeTab === 'detected' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-xs text-slate-400">
                  {ui("ui_scanned_your_local_disk_for_common_comfyui_webui")}</p>
                <button
                  onClick={scanForEngines}
                  disabled={isScanning}
                  className="inline-flex items-center space-x-1 px-2.5 py-1 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded transition-colors"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
                  <span>{ui("ui_rescan")}</span>
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
                  <p className="text-sm font-semibold text-slate-300">{ui("ui_no_external_engines_detected")}</p>
                  <p className="text-xs text-slate-500 mt-1 max-w-sm">
                    {ui("ui_no_installations_were_found_in_standard_directories_you")}</p>
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
                              {item.has_python_env ? ui("ui_isolated_venv_detected") : ui("ui_standard_environment")}
                            </span>
                          </div>
                        </div>
                      </div>

                      <button
                        onClick={() => handleBindDetected(item)}
                        className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-xs font-medium text-white rounded-lg transition-colors ml-4 whitespace-nowrap"
                      >
                        {ui("ui_bind_engine")}</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'browse' && (
            <form onSubmit={handleManualSubmit} className="space-y-4">
              <p className="text-xs text-slate-400">
                {ui("ui_specify_the_absolute_root_folder_of_an_existing")}</p>

              {manualError && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400 flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{manualError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">{ui("ui_engine_type")}</label>
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
                    <span>{ui("ui_comfyui")}</span>
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
                    <span>{ui("ui_sd_webui")}</span>
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">{ui("ui_directory_path")}</label>
                <input
                  type="text"
                  value={manualPath}
                  onChange={(e) => setManualPath(e.target.value)}
                  placeholder={ui("ui_e_g_d_comfyui_windows_portable_comfyui")}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">{ui("ui_display_name_optional")}</label>
                  <input
                    type="text"
                    value={manualName}
                    onChange={(e) => setManualName(e.target.value)}
                    placeholder={ui("ui_my_custom_engine")}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">{ui("ui_port")}</label>
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
                  {isSubmittingManual ? ui("ui_validating") : ui("ui_bind_directory")}
                </button>
              </div>
            </form>
          )}

          {activeTab === 'install' && (
            <div className="space-y-4">
              <p className="text-xs text-slate-400">
                {ui("ui_install_a_sandboxed_isolated_engine_environment_with_zero")}</p>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">{ui("ui_target_engine")}</label>
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
                    <span>{ui("ui_comfyui_recommended")}</span>
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
                    <span>{ui("ui_sd_webui")}</span>
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  {ui("ui_network_acceleration_mirror")}</label>
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
                        {ui("ui_china_mainland_accelerated_recommended_for_cn_users")}</div>
                      <div className="text-[11px] text-slate-400">
                        {ui("ui_uses_ghproxy_tsinghua_pip_mirror_and_hf_mirror")}</div>
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
                        {ui("ui_direct_official_sources")}</div>
                      <div className="text-[11px] text-slate-400">
                        {ui("ui_direct_connection_to_github_pypi_org_and_huggingface")}</div>
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
                  <span>{ui("ui_start_managed_installation")}</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </Dialog>
  );
};
