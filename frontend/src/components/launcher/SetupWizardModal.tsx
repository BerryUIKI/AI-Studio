import { useUiText } from '../../i18n/useUiText';
import { ProgressBar } from '../ui/ProgressBar';
import { listDownloadTasks } from '../../api/modelDownloads';
import { errorMessage as getErrorMessage } from '../../utils/errors';
import { Dialog } from '../ui/Dialog';
import React, { useEffect, useState } from 'react';
import {
  Sparkles,
  Cpu,
  HardDrive,
  Download,
  CheckCircle2,
  AlertCircle,
  X,
  Play,
  RotateCw,
  Zap,
  RefreshCw,
} from 'lucide-react';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { t } from '../../i18n/translations';

interface GpuDetail {
  index?: number;
  name: string;
  vram_total_mb: number;
  vram_free_mb: number;
  driver_version?: string | null;
  temperature_c?: number | null;
  vendor?: string;
  backend?: string;
  status_classification?: string;
}

interface HardwareInfo {
  has_nvidia_gpu: boolean;
  has_discrete_gpu: boolean;
  gpu_vendor: string;
  acceleration_backend: string;
  gpus: GpuDetail[];
  ram_total_mb: number;
  ram_avail_mb: number;
  engine_storage?: {
    path?: string;
    total_gb: number;
    free_gb: number;
    used_gb?: number;
    is_sufficient: boolean;
  };
  model_storage?: {
    path?: string;
    total_gb: number;
    free_gb: number;
    used_gb?: number;
    is_sufficient: boolean;
  };
  recommended_engine?: string;
  summary_message: string;
  guidance_notes?: string[];
  recommended_llm_models: string[];
}

interface LlamaModelInfo {
  name: string;
  path: string;
  size_bytes: number;
  modified_at?: string;
  status: string;
}

interface LlamaServerStatus {
  installed: boolean;
  running: boolean;
  pid?: number;
  port: number;
  endpoint: string;
  active_model?: string;
  models: LlamaModelInfo[];
}

interface SetupWizardModalProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigateToAgent?: () => void;
}

interface PresetModelDef {
  name: string;
  hubModelId: string;
  labelZh: string;
  labelEn: string;
  size: string;
  vramReqMb: number;
  descZh: string;
  descEn: string;
}

const PRESET_MODELS: PresetModelDef[] = [
  {
    name: 'qwen2.5:7b',
    hubModelId: 'qwen2.5-7b-instruct-q4_k_m',
    labelZh: 'Qwen 2.5 (7B) - 旗舰首选 [GGUF]',
    labelEn: 'Qwen 2.5 (7B) - Balanced [GGUF]',
    size: '4.7 GB',
    vramReqMb: 6144,
    descZh: '阿里千问最新高智商模型，完美支持多语言创意扩写与工作流编排，与画布100%通用。',
    descEn: 'Optimal balance of speed and intelligence for creative workflows, shared with canvas.',
  },
  {
    name: 'qwen2.5:1.5b',
    hubModelId: 'qwen2.5-1.5b-instruct-q4_k_m',
    labelZh: 'Qwen 2.5 (1.5B) - 轻量秒开 [GGUF]',
    labelEn: 'Qwen 2.5 (1.5B) - Ultra Fast [GGUF]',
    size: '1.0 GB',
    vramReqMb: 2048,
    descZh: '极低显存占用，秒级极速响应，适合轻薄本或低显存设备进行基础扩写与辅助控制。',
    descEn: 'Ultra-lightweight model with minimal memory requirements.',
  },
  {
    name: 'deepseek-r1:8b',
    hubModelId: 'deepseek-r1-distill-qwen-7b-q4_k_m',
    labelZh: 'DeepSeek R1 (7B) - 深度推理 [GGUF]',
    labelEn: 'DeepSeek R1 (7B) - Deep Reasoning [GGUF]',
    size: '4.7 GB',
    vramReqMb: 6144,
    descZh: '深度强化学习强力推理模型，长思考链路，擅长复杂提示词逻辑设计与工作流诊断。',
    descEn: 'DeepSeek R1 reasoning architecture for complex creative prompt composition.',
  },
];

export const SetupWizardModal: React.FC<SetupWizardModalProps> = ({
  isOpen,
  onClose,
  onNavigateToAgent,
}) => {
  const ui = useUiText();
  const { getEffectiveLanguage } = useSettingsStore();
  const lang = getEffectiveLanguage();
  const isZh = lang === 'zh-CN';

  const [activeStep, setActiveStep] = useState<1 | 2 | 3>(1);
  const [hardware, setHardware] = useState<HardwareInfo | null>(null);
  const [loadingHardware, setLoadingHardware] = useState(false);
  const [hardwareError, setHardwareError] = useState<string | null>(null);

  const [llamaStatus, setLlamaStatus] = useState<LlamaServerStatus | null>(null);
  const [loadingLlama, setLoadingLlama] = useState(false);
  const [installingLlama, setInstallingLlama] = useState(false);
  const [installMessage, setInstallMessage] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('qwen2.5:7b');
  const [isPulling, setIsPulling] = useState(false);
  const [pullProgress, setPullProgress] = useState<{ status: string; percent: number }>({
    status: '',
    percent: 0,
  });
  const [pullError, setPullError] = useState<string | null>(null);

  const fetchDiagnostics = async () => {
    setLoadingHardware(true);
    setHardwareError(null);

    try {
      const hwRes = await fetch('/api/v1/hardware/readiness');
      if (hwRes.ok) {
        const hwData: HardwareInfo = await hwRes.json();
        setHardware(hwData);
        if (hwData.recommended_llm_models && hwData.recommended_llm_models.length > 0) {
          const topChoice = hwData.recommended_llm_models[0];
          if (PRESET_MODELS.some((m) => m.name === topChoice)) {
            setSelectedModel(topChoice);
          }
        }
      } else {
        setHardwareError(`HTTP ${hwRes.status}: ${hwRes.statusText}`);
      }
    } catch (e: unknown) {
      console.warn('Failed to fetch hardware readiness:', e);
      setHardwareError(getErrorMessage(e, ui("ui_connection_refused_127_0_0_1_8000")));
    } finally {
      setLoadingHardware(false);
    }

    try {
      const llamaRes = await fetch('/api/v1/llama-server/status');
      if (llamaRes.ok) {
        const llamaData: LlamaServerStatus = await llamaRes.json();
        setLlamaStatus(llamaData);
      }
    } catch (e) {
      console.warn('Failed to fetch llama-server status:', e);
    } finally {
      setLoadingLlama(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchDiagnostics();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleStartLlama = async () => {
    setLoadingLlama(true);
    setStartError(null);
    try {
      const res = await fetch('/api/v1/llama-server/start', { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!data.success) {
        setStartError(data.message || (ui("ui_failed_to_start_llama_server")));
      }
      await fetchDiagnostics();
    } catch (e: unknown) {
      setStartError(getErrorMessage(e, ui("ui_start_failed")));
    } finally {
      setLoadingLlama(false);
    }
  };

  const handleInstallLlama = async () => {
    setInstallingLlama(true);
    setInstallMessage(ui("ui_initializing_embedded_llama_cpp_runtime"));
    try {
      const res = await fetch('/api/v1/llama-server/install', { method: 'POST' });
      const data = await res.json();
      if (data.installed) {
        setInstallMessage(ui("ui_embedded_llama_server_runtime_is_ready"));
      } else {
        setInstallMessage(data.message || (ui("ui_check_completed")));
      }
      setTimeout(() => fetchDiagnostics(), 1500);
    } catch (e: unknown) {
      setInstallMessage(getErrorMessage(e, ui("ui_failed_to_initialize")));
    } finally {
      setInstallingLlama(false);
    }
  };

  const handlePullModel = async (modelName: string) => {
    setIsPulling(true);
    setPullError(null);

    const preset = PRESET_MODELS.find((m) => m.name === modelName);

    // If preset has hubModelId, use the robust multi-mirror GGUF downloader
    if (preset?.hubModelId) {
      setPullProgress({ status: ui("ui_resolving_model_mirrors"), percent: 0 });
      try {
        // Auto-install llama-server binary if not present
        if (!llamaStatus?.installed) {
          setPullProgress({ status: ui("ui_deploying_llama_cpp_runtime"), percent: 5 });
          await fetch('/api/v1/llama-server/install', { method: 'POST' }).catch(() => {});
        }

        const startRes = await fetch('/api/v1/models/hub/download', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model_id: preset.hubModelId, target_engine: 'llama_server' }),
        });

        if (!startRes.ok) {
          const errData = await startRes.json().catch(() => ({}));
          throw new Error(errData.detail || `HTTP ${startRes.status}`);
        }

        const taskInfo = await startRes.json();
        const taskId = taskInfo.task_id;

        // Poll task progress
        let completed = false;
        while (!completed) {
          await new Promise((r) => setTimeout(r, 800));
          const tasks = await listDownloadTasks();
          const currentTask = tasks.find((task) => task.task_id === taskId);
          if (!currentTask) continue;

          if (currentTask.status === 'downloading' || currentTask.status === 'pending') {
            const speedMb = currentTask.speed_bps ? (currentTask.speed_bps / (1024 * 1024)).toFixed(1) : '0';
            const statusMsg = ui("ui_downloading_value_mb_s_to_engine_models_llm", { value1: speedMb });
            setPullProgress({
              status: statusMsg,
              percent: Math.min(99, Math.round(currentTask.progress_pct || 0)),
            });
          } else if (currentTask.status === 'completed') {
            completed = true;
            setPullProgress({ status: ui("ui_model_verified_starting_engine"), percent: 100 });
          } else if (currentTask.status === 'failed') {
            throw new Error(currentTask.error_message || ui("ui_download_failed"));
          }
        }

        // Auto-start llama-server with the new model
        await fetch('/api/v1/llama-server/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model_name: preset.hubModelId }),
        }).catch(() => {});

        // Configure default LLM provider to llama_server
        await fetch('/api/v1/cloud/llm/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            provider: 'llama_server',
            model: preset.name,
            base_url: 'http://127.0.0.1:8080/v1',
            enabled: true,
          }),
        }).catch(() => {});

        setIsPulling(false);
        await fetchDiagnostics();
        setActiveStep(3);
        return;
      } catch (err: unknown) {
        setPullError(getErrorMessage(err, ui("ui_model_download_failed")));
        setIsPulling(false);
        return;
      }
    }

    if (!preset?.hubModelId) {
      setPullError(ui("ui_gguf_model_configuration_not_found"));
      setIsPulling(false);
      return;
    }
  };

  // Find the discrete high-performance GPU first, falling back to index 0
  const primaryGpu: GpuDetail | undefined =
    hardware?.gpus?.find(
      (g) => g.backend === 'cuda' || g.vendor === 'nvidia' || g.vendor === 'amd' || g.vram_total_mb > 2048
    ) || hardware?.gpus?.[0];

  const gpuNameDisplay = primaryGpu?.name || (ui("ui_no_dedicated_gpu"));
  const totalVramGb = primaryGpu ? Math.round(primaryGpu.vram_total_mb / 1024) : 0;
  const freeVramGb = primaryGpu ? (primaryGpu.vram_free_mb / 1024).toFixed(1) : '0';
  const usedVramGb = primaryGpu ? ((primaryGpu.vram_total_mb - primaryGpu.vram_free_mb) / 1024).toFixed(1) : '0';
  const vramPercent =
    primaryGpu && primaryGpu.vram_total_mb > 0
      ? Math.min(100, Math.round(((primaryGpu.vram_total_mb - primaryGpu.vram_free_mb) / primaryGpu.vram_total_mb) * 100))
      : 0;

  const totalRamGb = hardware ? Math.round(hardware.ram_total_mb / 1024) : 0;
  const availRamGb = hardware ? (hardware.ram_avail_mb / 1024).toFixed(1) : '0';
  const ramPercent =
    hardware && hardware.ram_total_mb > 0
      ? Math.min(100, Math.round(((hardware.ram_total_mb - hardware.ram_avail_mb) / hardware.ram_total_mb) * 100))
      : 0;

  const storageFreeGb = hardware?.engine_storage?.free_gb ?? 0;
  const storageTotalGb = hardware?.engine_storage?.total_gb ?? 0;
  const storagePath = hardware?.engine_storage?.path || '';

  // Dynamic headline for Step 2
  const gpuDescHeadline = primaryGpu
    ? `${primaryGpu.name} (${totalVramGb}GB VRAM)`
    : (ui("ui_cpu_mode"));
  const ramDescHeadline = hardware
    ? `${totalRamGb}GB RAM`
    : (ui("ui_host_ram"));

  return (
    <Dialog title={ui("ui_setup_guide")} onClose={onClose} className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md select-none animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col text-slate-100 max-h-[90vh]">
        {/* Header */}
        <div className="p-5 border-b border-white/[0.08] flex items-center justify-between bg-slate-900/60">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20 text-white">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <span>{t('setup_wizard_title', lang, (ui("ui_hardware_diagnostics_model_setup")))}</span>
                <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  {ui("ui_embedded_llama_cpp")}</span>
              </h2>
              <p className="text-xs text-slate-400">
                {t('setup_wizard_subtitle', lang, (ui("ui_live_gpu_diagnosis_embedded_llama_cpp_lifecycle_instant")))}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label={ui("ui_close_dialog")}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Step Indicator */}
        <div className="grid grid-cols-3 border-b border-white/[0.06] bg-slate-950/40 text-xs">
          <button
            onClick={() => setActiveStep(1)}
            className={`py-2.5 px-4 flex items-center justify-center space-x-2 border-b-2 font-medium transition-colors ${
              activeStep === 1
                ? 'border-indigo-500 text-indigo-400 bg-indigo-500/5'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span>{t('setup_step_hardware', lang, (ui("ui_1_hardware_check")))}</span>
          </button>
          <button
            onClick={() => setActiveStep(2)}
            className={`py-2.5 px-4 flex items-center justify-center space-x-2 border-b-2 font-medium transition-colors ${
              activeStep === 2
                ? 'border-indigo-500 text-indigo-400 bg-indigo-500/5'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Download className="w-3.5 h-3.5" />
            <span>{t('setup_step_model', lang, (ui("ui_2_deploy_model")))}</span>
          </button>
          <button
            onClick={() => setActiveStep(3)}
            className={`py-2.5 px-4 flex items-center justify-center space-x-2 border-b-2 font-medium transition-colors ${
              activeStep === 3
                ? 'border-indigo-500 text-indigo-400 bg-indigo-500/5'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>{t('setup_step_ready', lang, (ui("ui_3_ready")))}</span>
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {/* STEP 1: Hardware Diagnostics */}
          {activeStep === 1 && (
            <div className="space-y-4">
              {/* Header bar with Refresh button */}
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="font-medium text-slate-300">
                  {ui("ui_live_hardware_telemetry")}
                </span>
                <button
                  onClick={fetchDiagnostics}
                  disabled={loadingHardware}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 hover:text-white border border-slate-700/60 transition shadow-sm"
                  title={ui("ui_refresh_hardware_telemetry")}
                >
                  <RefreshCw className={`w-3 h-3 ${loadingHardware ? 'animate-spin text-indigo-400' : ''}`} />
                  <span>{loadingHardware ? (ui("ui_scanning")) : (ui("ui_rescan"))}</span>
                </button>
              </div>

              {/* Hardware Connection Error Banner */}
              {hardwareError && !hardware && (
                <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-500/30 text-rose-300 space-y-2 text-xs">
                  <div className="flex items-center gap-2 font-semibold text-rose-200">
                    <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                    <span>{ui("ui_backend_hardware_telemetry_unavailable")}</span>
                  </div>
                  <p className="text-[11px] text-rose-300/90 leading-relaxed">
                    {ui("ui_the_core_backend_service_is_not_yet_responding")}
                  </p>
                  <button
                    onClick={fetchDiagnostics}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600/30 hover:bg-rose-600/50 border border-rose-500/40 text-white font-medium text-xs transition"
                  >
                    <RefreshCw className="w-3 h-3" />
                    <span>{ui("ui_retry_connection")}</span>
                  </button>
                </div>
              )}

              {/* Hardware Diagnostic Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* GPU Card */}
                <div className="p-4 rounded-xl bg-slate-800/40 border border-white/[0.06] flex flex-col justify-between">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
                      <Cpu className="w-4 h-4 text-indigo-400" />
                      {ui("ui_graphics_processor")}
                    </span>
                    {primaryGpu ? (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-semibold tracking-wide border border-emerald-500/30">
                        {primaryGpu.vendor ? `${primaryGpu.vendor.toUpperCase()} ${primaryGpu.backend?.toUpperCase() || ''}`.trim() : ui("ui_gpu_accel")}
                      </span>
                    ) : (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-medium border border-amber-500/30">
                        {ui("ui_cpu_mode_2")}</span>
                    )}
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white truncate" title={gpuNameDisplay}>
                      {gpuNameDisplay}
                    </div>
                    {primaryGpu ? (
                      <div className="space-y-1.5 mt-2">
                        <div className="flex items-center justify-between text-xs text-slate-300 font-mono">
                          <span>
                            {ui("ui_vram")}: <strong className="text-indigo-300">{totalVramGb} {ui("ui_gb")}</strong>
                          </span>
                          <span className="text-slate-400 text-[11px]">
                            {ui("ui_free_valueg", { value1: freeVramGb })} / {ui("ui_used_valueg", { value1: usedVramGb })}
                          </span>
                        </div>
                        {/* VRAM Bar */}
                        <div className="w-full h-1.5 rounded-full bg-slate-700/60 overflow-hidden">
                          <ProgressBar label={ui("ui_observed_progress")} value={vramPercent} className={`h-full transition-all duration-300 ${
                              vramPercent > 85 ? 'text-rose-500' : vramPercent > 60 ? 'text-amber-400' : 'text-emerald-400'
                            }`} />
                        </div>
                        <div className="flex items-center gap-3 text-[10px] text-slate-400 pt-0.5">
                          {primaryGpu.driver_version && (
                            <span>{ui("ui_driver_2")}: {primaryGpu.driver_version}</span>
                          )}
                          {primaryGpu.temperature_c !== null && primaryGpu.temperature_c !== undefined && (
                            <span>{ui("ui_temp")}: {primaryGpu.temperature_c}{ui("ui_c")}</span>
                          )}
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-slate-400 mt-1">
                        {ui("ui_fallback_to_cpu_execution")}
                      </p>
                    )}
                  </div>
                </div>

                {/* RAM Card */}
                <div className="p-4 rounded-xl bg-slate-800/40 border border-white/[0.06] flex flex-col justify-between">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
                      <Zap className="w-4 h-4 text-purple-400" />
                      {ui("ui_system_memory")}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 font-medium border border-purple-500/30">
                      {ui("ui_host_ram")}</span>
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white">
                      {hardware ? ui("ui_value_gb_ram", { value1: totalRamGb }) : (ui("ui_reading_ram"))}
                    </div>
                    {hardware ? (
                      <div className="space-y-1.5 mt-2">
                        <div className="flex items-center justify-between text-xs text-slate-300 font-mono">
                          <span>
                            {ui("ui_available")}: <strong className="text-purple-300">{availRamGb} {ui("ui_gb")}</strong>
                          </span>
                          <span className="text-slate-400 text-[11px]">{ramPercent}% {ui("ui_used")}</span>
                        </div>
                        <div className="w-full h-1.5 rounded-full bg-slate-700/60 overflow-hidden">
                          <ProgressBar label={ui("ui_observed_progress")} value={ramPercent} className="h-full text-purple-500 transition-all duration-300" />
                        </div>
                        <p className="text-[10px] text-slate-400 pt-0.5">
                          {isZh
                            ? totalRamGb >= 16 ? '内存充裕，支持同时加载大模型与绘图管道' : '建议部署轻量模型避免内存超载'
                            : totalRamGb >= 16 ? ui("ui_ample_memory_for_models_workflows") : ui("ui_lightweight_model_recommended")}
                        </p>
                      </div>
                    ) : (
                      <p className="text-xs text-slate-400 mt-1">
                        {ui("ui_querying_host_system_ram")}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Storage & Readiness Banner */}
              <div className="p-4 rounded-xl bg-slate-800/20 border border-white/[0.06] space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400 flex items-center gap-1.5">
                    <HardDrive className="w-3.5 h-3.5 text-slate-400" />
                    <span>{ui("ui_disk_storage")}</span>
                  </span>
                  <span className="text-slate-300 font-mono text-xs">
                    {hardware ? (
                      <>
                        <strong className="text-slate-100">{storageFreeGb.toFixed(1)} {ui("ui_gb")}</strong>{' '}
                        {ui("ui_free")} / {storageTotalGb.toFixed(0)} {ui("ui_gb")}</>
                    ) : (
                      '...'
                    )}
                  </span>
                </div>
                {storagePath && (
                  <p className="text-[11px] font-mono text-slate-500 truncate" title={storagePath}>
                    {storagePath}
                  </p>
                )}
                <div className="p-3 rounded-lg bg-indigo-950/40 border border-indigo-500/20 text-xs text-indigo-200 leading-relaxed">
                  {hardware?.summary_message ||
                    (loadingHardware
                      ? (ui("ui_evaluating_hardware_compatibility"))
                      : (ui("ui_start_backend_service_to_load_hardware_specs")))}
                </div>
                {hardware?.guidance_notes && hardware.guidance_notes.length > 0 && (
                  <ul className="text-[11px] text-slate-400 space-y-1 list-disc pl-4 pt-1">
                    {hardware.guidance_notes.map((note, idx) => (
                      <li key={idx}>{note}</li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Embedded llama.cpp Server Status Card (Primary Recommended) */}
              <div className="p-4 rounded-xl bg-slate-800/40 border border-white/[0.06] space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="w-9 h-9 rounded-lg bg-indigo-950/80 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
                      <Cpu className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-white flex items-center gap-2">
                        <span>{ui("ui_embedded_llama_cpp_server_zero_host_pollution")}</span>
                        {llamaStatus?.running ? (
                          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                        ) : !llamaStatus?.installed ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-medium">
                            {ui("ui_not_initialized")}
                          </span>
                        ) : (
                          <span className="w-2 h-2 rounded-full bg-slate-400" />
                        )}
                      </div>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        {llamaStatus?.running
                          ? (ui("ui_active_on_port_value_shared_gguf", { value1: llamaStatus.port }))
                          : !llamaStatus?.installed
                          ? (ui("ui_binary_ready_for_automatic_setup"))
                          : (ui("ui_ready_to_start_on_demand"))}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    {!llamaStatus?.installed ? (
                      <button
                        onClick={handleInstallLlama}
                        disabled={installingLlama}
                        className="flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-medium rounded-lg transition shadow-sm"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>{installingLlama ? (ui("ui_installing")) : (ui("ui_init_engine"))}</span>
                      </button>
                    ) : !llamaStatus?.running ? (
                      <button
                        onClick={handleStartLlama}
                        disabled={loadingLlama}
                        className="flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-medium rounded-lg transition-colors shadow-sm"
                      >
                        <Play className="w-3.5 h-3.5" />
                        <span>{loadingLlama ? (ui("ui_starting")) : (ui("ui_start_service"))}</span>
                      </button>
                    ) : (
                      <span className="text-xs text-emerald-400 font-medium flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>{ui("ui_running")}</span>
                      </span>
                    )}
                  </div>
                </div>

                {(installMessage || startError) && (
                  <div className={`p-2.5 rounded-lg text-xs border ${startError ? 'bg-rose-950/40 border-rose-500/30 text-rose-300' : 'bg-indigo-950/30 border-indigo-500/20 text-indigo-300'}`}>
                    {startError || installMessage}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* STEP 2: Deploy Model */}
          {activeStep === 2 && (
            <div className="space-y-4">
              <div className="p-3 rounded-lg bg-indigo-950/30 border border-indigo-500/20 text-xs text-slate-200 leading-relaxed">
                <span className="text-indigo-300 font-semibold">{ui("ui_hardware_telemetry")}</span>
                <span>
                  {ui("ui_based_on_your_live_hardware_telemetry_value_value", { value1: gpuDescHeadline, value2: ramDescHeadline })}
                </span>
              </div>

              <div className="space-y-2.5">
                {PRESET_MODELS.map((model) => {
                  const isSelected = selectedModel === model.name;
                  const isAlreadyInstalled = llamaStatus?.models?.some(
                    (m) =>
                      m.name.toLowerCase().includes(model.name.split(':')[0].toLowerCase()) ||
                      (model.hubModelId && m.name.includes(model.hubModelId))
                  );

                  // Dynamic match check: does hardware support full GPU or RAM?
                  const fitsGpu = primaryGpu && primaryGpu.vram_total_mb >= model.vramReqMb;
                  const fitsRam = hardware && hardware.ram_avail_mb >= model.vramReqMb;
                  const isRecommended = hardware?.recommended_llm_models?.includes(model.name) ?? false;

                  return (
                    <div
                      key={model.name}
                      onClick={() => !isPulling && setSelectedModel(model.name)}
                      className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between ${
                        isSelected
                          ? 'bg-indigo-600/10 border-indigo-500 shadow-md shadow-indigo-500/10'
                          : 'bg-slate-800/40 border-white/[0.06] hover:bg-slate-800/70'
                      }`}
                    >
                      <div className="space-y-1 flex-1 pr-3">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-white">
                            {ui.lookup(model.labelEn)}
                          </span>
                          {isRecommended && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-medium">
                              {ui("ui_optimal")}
                            </span>
                          )}
                          {isAlreadyInstalled && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-medium">
                              {ui("ui_installed")}
                            </span>
                          )}
                          {fitsGpu ? (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 font-mono">
                              {ui("ui_gpu_max")}
                            </span>
                          ) : fitsRam ? (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-300 font-mono">
                              {ui("ui_ram_hybrid")}
                            </span>
                          ) : (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-700/40 text-slate-400 font-mono">
                              {ui("ui_heavy_load")}
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-slate-400">
                          {ui.lookup(model.descEn)}
                        </p>
                        <div className="flex items-center gap-3 text-[10px] text-slate-500 pt-0.5">
                          <span>{ui("ui_download_size")}: {model.size}</span>
                          <span>•</span>
                          <span>{ui("ui_vram_req")}: {Math.round(model.vramReqMb / 1024)} {ui("ui_gb_2")}</span>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2 shrink-0">
                        {isAlreadyInstalled ? (
                          <span className="text-xs text-emerald-400 font-medium flex items-center gap-1">
                            <CheckCircle2 className="w-4 h-4" />
                          </span>
                        ) : (
                          <div
                            className={`w-4 h-4 rounded-full border flex items-center justify-center transition-colors ${
                              isSelected ? 'border-indigo-400 bg-indigo-600' : 'border-slate-600'
                            }`}
                          >
                            {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Download / Pull Progress */}
              {isPulling && (
                <div className="p-4 rounded-xl bg-slate-950/80 border border-indigo-500/30 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-indigo-300 flex items-center gap-2 font-medium">
                      <RotateCw className="w-3.5 h-3.5 animate-spin" />
                      {pullProgress.status || (ui("ui_pulling_model"))}
                    </span>
                    <span className="text-white font-mono font-bold">{pullProgress.percent}%</span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                    <ProgressBar label={ui("ui_observed_progress")} value={pullProgress.percent} className="h-full text-indigo-500 transition-all duration-300" />
                  </div>
                </div>
              )}

              {pullError && (
                <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-500/30 text-xs text-rose-300 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{pullError}</span>
                </div>
              )}
            </div>
          )}

          {/* STEP 3: Ready */}
          {activeStep === 3 && (
            <div className="py-6 flex flex-col items-center justify-center text-center space-y-4">
              <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center text-emerald-400 shadow-xl shadow-emerald-500/10">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <div className="space-y-1 max-w-md">
                <h3 className="text-base font-bold text-white">
                  {ui("ui_local_model_agent_base_ready")}
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  {ui("ui_your_local_llm_is_now_running_seamlessly_with")}
                </p>
              </div>

              {llamaStatus?.models && llamaStatus.models.length > 0 && (
                <div className="w-full max-w-sm p-3 rounded-xl bg-slate-800/40 border border-white/[0.06] text-left text-xs">
                  <div className="font-semibold text-slate-300 mb-1">
                    {ui("ui_loaded_gguf_models")}
                  </div>
                  <div className="space-y-1">
                    {llamaStatus.models.map((m) => (
                      <div key={m.name} className="flex justify-between text-slate-400 font-mono text-[11px]">
                        <span>• {m.name}</span>
                        <span>{Math.round((m.size_bytes / (1024 * 1024 * 1024)) * 10) / 10} {ui("ui_gb")}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Navigation */}
        <div className="p-4 border-t border-white/[0.08] bg-slate-900/60 flex items-center justify-between">
          <div>
            {activeStep > 1 && (
              <button
                onClick={() => setActiveStep((prev) => prev === 3 ? 2 : 1)}
                disabled={isPulling}
                className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white transition-colors"
              >
                {ui("ui_back")}
              </button>
            )}
          </div>

          <div className="flex items-center space-x-2.5">
            {activeStep === 1 && (
              <button
                onClick={() => setActiveStep(2)}
                className="flex items-center space-x-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-600/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
              >
                <span>{ui("ui_next_select_deploy")}</span>
              </button>
            )}

            {activeStep === 2 && (
              <button
                onClick={() => handlePullModel(selectedModel)}
                disabled={isPulling}
                className="flex items-center space-x-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-600/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
              >
                <Download className="w-4 h-4" />
                <span>
                  {isPulling
                    ? (ui("ui_pulling_model_2"))
                    : (ui("ui_deploy_value", { value1: selectedModel }))}
                </span>
              </button>
            )}

            {activeStep === 3 && (
              <button
                onClick={() => {
                  onClose();
                  onNavigateToAgent?.();
                }}
                className="flex items-center space-x-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-600/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
              >
                <Sparkles className="w-4 h-4" />
                <span>{ui("ui_open_ai_agent_now")}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </Dialog>
  );
};
