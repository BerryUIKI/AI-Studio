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
  Server,
  Zap,
  RefreshCw,
  ExternalLink,
} from 'lucide-react';
import { useSettingsStore } from '../../stores/useSettingsStore';

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

interface OllamaStatus {
  installed: boolean;
  running: boolean;
  pid?: number;
  port?: number;
  endpoint: string;
  models: Array<{
    name: string;
    size_bytes: number;
    parameter_size?: string;
  }>;
}

interface SetupWizardModalProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigateToAgent?: () => void;
}

interface PresetModelDef {
  name: string;
  labelZh: string;
  labelEn: string;
  size: string;
  vramReqMb: number;
  descZh: string;
  descEn: string;
}

const PRESET_MODELS: PresetModelDef[] = [
  {
    name: 'qwen2.5:14b',
    labelZh: 'Qwen 2.5 (14B) - 高阶旗舰',
    labelEn: 'Qwen 2.5 (14B) - Flagship',
    size: '9.0 GB',
    vramReqMb: 12288,
    descZh: '14B 强大中文与多语言旗舰，深度理解复杂画作创作意图与复杂节点工作流',
    descEn: 'High-capability 14B model for nuanced prompt generation & workflow control.',
  },
  {
    name: 'qwen2.5:7b',
    labelZh: 'Qwen 2.5 (7B) - 均衡首选',
    labelEn: 'Qwen 2.5 (7B) - Balanced',
    size: '4.7 GB',
    vramReqMb: 6144,
    descZh: '阿里千问最新高智商模型，完美支持多语言创意扩写与工作流编排',
    descEn: 'Optimal balance of speed and intelligence for creative workflows.',
  },
  {
    name: 'deepseek-r1:14b',
    labelZh: 'DeepSeek R1 (14B) - 强推理旗舰',
    labelEn: 'DeepSeek R1 (14B) - Deep Reasoning',
    size: '9.0 GB',
    vramReqMb: 12288,
    descZh: '深度强化学习强力推理模型，严谨构图审美与逻辑细节规划',
    descEn: 'Advanced reasoning model with deep chain-of-thought planning.',
  },
  {
    name: 'deepseek-r1:8b',
    labelZh: 'DeepSeek R1 (8B) - 深度推理',
    labelEn: 'DeepSeek R1 (8B) - Reasoning',
    size: '4.9 GB',
    vramReqMb: 6144,
    descZh: '深度强化学习推理模型，长思考链路，擅长复杂提示词逻辑设计',
    descEn: 'DeepSeek R1 reasoning architecture for complex creative prompt composition.',
  },
  {
    name: 'llama3.2:3b',
    labelZh: 'Llama 3.2 (3B) - 轻量极速',
    labelEn: 'Llama 3.2 (3B) - Lightweight',
    size: '2.0 GB',
    vramReqMb: 3072,
    descZh: 'Meta 超轻量高效模型，启动迅捷，可在低显存或CPU流畅运行',
    descEn: 'Ultra-lightweight Meta model, ultra-fast and CPU/low-VRAM friendly.',
  },
];

export const SetupWizardModal: React.FC<SetupWizardModalProps> = ({
  isOpen,
  onClose,
  onNavigateToAgent,
}) => {
  const { getEffectiveLanguage } = useSettingsStore();
  const lang = getEffectiveLanguage();
  const isZh = lang === 'zh-CN';

  const [activeStep, setActiveStep] = useState<1 | 2 | 3>(1);
  const [hardware, setHardware] = useState<HardwareInfo | null>(null);
  const [loadingHardware, setLoadingHardware] = useState(false);
  const [hardwareError, setHardwareError] = useState<string | null>(null);

  const [ollamaStatus, setOllamaStatus] = useState<OllamaStatus | null>(null);
  const [loadingOllama, setLoadingOllama] = useState(false);
  const [installingOllama, setInstallingOllama] = useState(false);
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
    setLoadingOllama(true);
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
    } catch (e: any) {
      console.warn('Failed to fetch hardware readiness:', e);
      setHardwareError(e?.message || 'Connection refused (127.0.0.1:8000)');
    } finally {
      setLoadingHardware(false);
    }

    try {
      const olRes = await fetch('/api/v1/ollama/status');
      if (olRes.ok) {
        const olData: OllamaStatus = await olRes.json();
        setOllamaStatus(olData);
      }
    } catch (e) {
      console.warn('Failed to fetch ollama status:', e);
    } finally {
      setLoadingOllama(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchDiagnostics();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleStartOllama = async () => {
    setLoadingOllama(true);
    setStartError(null);
    try {
      const res = await fetch('/api/v1/ollama/start', { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!data.success) {
        setStartError(data.message || (isZh ? '启动 Ollama 失败' : 'Failed to start Ollama'));
      }
      await fetchDiagnostics();
    } catch (e: any) {
      console.error(e);
      setStartError(e?.message || (isZh ? '启动失败' : 'Start failed'));
    } finally {
      setLoadingOllama(false);
    }
  };

  const handleInstallOllama = async () => {
    setInstallingOllama(true);
    setInstallMessage(isZh ? '正在检查内置 Ollama 引擎状态...' : 'Checking embedded Ollama engine status...');
    try {
      const res = await fetch('/api/v1/ollama/install', { method: 'POST' });
      const data = await res.json();
      if (data.installed) {
        setInstallMessage(isZh ? '内置 Ollama 引擎已就绪。' : 'Embedded Ollama engine is ready.');
      } else if (data.target_dir) {
        setInstallMessage(
          isZh
            ? `请将 ollama 可执行文件放置于软件独立运行目录：${data.target_dir}，或点击右侧下载安装。`
            : `Place ollama into isolated directory: ${data.target_dir}`
        );
      } else {
        setInstallMessage(data.message || (isZh ? '已完成检查' : 'Check completed'));
      }
      setTimeout(() => fetchDiagnostics(), 2000);
    } catch (e: any) {
      setInstallMessage(e?.message || (isZh ? '请求检查失败' : 'Failed to check embedded status'));
    } finally {
      setInstallingOllama(false);
    }
  };

  const handlePullModel = async (modelName: string) => {
    setIsPulling(true);
    setPullError(null);

    // Guard: check if Ollama is installed
    if (ollamaStatus && !ollamaStatus.installed) {
      setPullError(
        isZh
          ? '未检测到 Ollama 运行环境。请先完成 Ollama 安装（可点击上方“一键安装”或前往官网下载）。'
          : 'Ollama is not installed. Please install Ollama from https://ollama.com first.'
      );
      setIsPulling(false);
      return;
    }

    setPullProgress({ status: isZh ? '正在建立下载连接...' : 'Connecting...', percent: 0 });

    try {
      const resp = await fetch('/api/v1/ollama/pull', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_name: modelName }),
      });

      if (!resp.ok) {
        throw new Error(`Server returned HTTP ${resp.status}`);
      }

      const reader = resp.body?.getReader();
      if (!reader) throw new Error('Readable stream not supported');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);
            if (data.error) {
              let errMsg = data.error;
              if (errMsg.includes('502') || errMsg.includes('actively refused') || errMsg.includes('ConnectError')) {
                errMsg = isZh
                  ? '无法连接到 Ollama 服务（服务未就绪或本地代理冲突）。后台正尝试拉起服务，请稍后重试。'
                  : 'Cannot connect to Ollama service. Please make sure Ollama is running.';
              } else if (errMsg.includes('not installed')) {
                errMsg = isZh
                  ? '未检测到 Ollama 运行环境，请先安装 Ollama 引擎。'
                  : 'Ollama is not installed. Please install Ollama first.';
              }
              setPullError(errMsg);
              setIsPulling(false);
              return;
            }
            const status = data.status || '';
            const total = data.total || 0;
            const completed = data.completed || 0;
            const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
            setPullProgress({ status, percent: pct });
          } catch {
            // ignore chunk JSON parse
          }
        }
      }

      setIsPulling(false);
      await fetchDiagnostics();
      setActiveStep(3);
    } catch (err: any) {
      let msg = err?.message || 'Download failed';
      if (msg.includes('502') || msg.includes('Failed to fetch')) {
        msg = isZh
          ? '拉取模型失败：无法连接到本地 Ollama 服务或代理劫持回环。请检查 Ollama 是否安装并启动。'
          : 'Failed to pull model: cannot connect to local Ollama service. Please ensure Ollama is installed and active.';
      }
      setPullError(msg);
      setIsPulling(false);
    }
  };

  // Find the discrete high-performance GPU first, falling back to index 0
  const primaryGpu: GpuDetail | undefined =
    hardware?.gpus?.find(
      (g) => g.backend === 'cuda' || g.vendor === 'nvidia' || g.vendor === 'amd' || g.vram_total_mb > 2048
    ) || hardware?.gpus?.[0];

  const gpuNameDisplay = primaryGpu?.name || (isZh ? '未检测到独立显卡' : 'No Dedicated GPU');
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
    : (isZh ? 'CPU 模式' : 'CPU Mode');
  const ramDescHeadline = hardware
    ? `${totalRamGb}GB RAM`
    : (isZh ? '主机内存' : 'Host RAM');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md select-none animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col text-slate-100 max-h-[90vh]">
        {/* Header */}
        <div className="p-5 border-b border-white/[0.08] flex items-center justify-between bg-slate-900/60">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20 text-white">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <span>{isZh ? '系统硬件体检与本地模型部署向导' : 'Hardware Diagnostics & Model Setup'}</span>
                <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  Built-in Ollama
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                {isZh
                  ? '一站式真实检测硬件配置、管理内置 Ollama 服务与极速部署本地大模型'
                  : 'Live GPU diagnosis, embedded Ollama lifecycle & instant local model provisioning'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
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
            <span>{isZh ? '1. 硬件配置体检' : '1. Hardware Check'}</span>
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
            <span>{isZh ? '2. 选择与部署模型' : '2. Deploy Model'}</span>
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
            <span>{isZh ? '3. 体验就绪' : '3. Ready'}</span>
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
                  {isZh ? '实时底层硬件规格' : 'Live Hardware Telemetry'}
                </span>
                <button
                  onClick={fetchDiagnostics}
                  disabled={loadingHardware}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 hover:text-white border border-slate-700/60 transition shadow-sm"
                  title="Refresh Hardware Telemetry"
                >
                  <RefreshCw className={`w-3 h-3 ${loadingHardware ? 'animate-spin text-indigo-400' : ''}`} />
                  <span>{loadingHardware ? (isZh ? '正在诊断...' : 'Scanning...') : (isZh ? '重新体检' : 'Rescan')}</span>
                </button>
              </div>

              {/* Hardware Connection Error Banner */}
              {hardwareError && !hardware && (
                <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-500/30 text-rose-300 space-y-2 text-xs">
                  <div className="flex items-center gap-2 font-semibold text-rose-200">
                    <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                    <span>{isZh ? '无法连接到后端硬件诊断服务' : 'Backend Hardware Telemetry Unavailable'}</span>
                  </div>
                  <p className="text-[11px] text-rose-300/90 leading-relaxed">
                    {isZh
                      ? '后端服务 (http://127.0.0.1:8000) 尚未就绪或连接被拒绝。正在启动后台进程，请稍候点击下方按钮重试。'
                      : 'The core backend service is not yet responding. Please ensure the local service is running.'}
                  </p>
                  <button
                    onClick={fetchDiagnostics}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600/30 hover:bg-rose-600/50 border border-rose-500/40 text-white font-medium text-xs transition"
                  >
                    <RefreshCw className="w-3 h-3" />
                    <span>{isZh ? '重试连接' : 'Retry Connection'}</span>
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
                      {isZh ? '图形显卡 (GPU)' : 'Graphics Processor'}
                    </span>
                    {primaryGpu ? (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-semibold tracking-wide border border-emerald-500/30">
                        {primaryGpu.vendor ? `${primaryGpu.vendor.toUpperCase()} ${primaryGpu.backend?.toUpperCase() || ''}`.trim() : 'GPU ACCEL'}
                      </span>
                    ) : (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-medium border border-amber-500/30">
                        CPU MODE
                      </span>
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
                            {isZh ? '显存' : 'VRAM'}: <strong className="text-indigo-300">{totalVramGb} GB</strong>
                          </span>
                          <span className="text-slate-400 text-[11px]">
                            {isZh ? `空闲 ${freeVramGb}G` : `Free ${freeVramGb}G`} / {isZh ? `占用 ${usedVramGb}G` : `Used ${usedVramGb}G`}
                          </span>
                        </div>
                        {/* VRAM Bar */}
                        <div className="w-full h-1.5 rounded-full bg-slate-700/60 overflow-hidden">
                          <div
                            className={`h-full transition-all duration-300 ${
                              vramPercent > 85 ? 'bg-rose-500' : vramPercent > 60 ? 'bg-amber-400' : 'bg-emerald-400'
                            }`}
                            style={{ width: `${vramPercent}%` }}
                          />
                        </div>
                        <div className="flex items-center gap-3 text-[10px] text-slate-400 pt-0.5">
                          {primaryGpu.driver_version && (
                            <span>{isZh ? '驱动版本' : 'Driver'}: {primaryGpu.driver_version}</span>
                          )}
                          {primaryGpu.temperature_c !== null && primaryGpu.temperature_c !== undefined && (
                            <span>{isZh ? '核心温度' : 'Temp'}: {primaryGpu.temperature_c}°C</span>
                          )}
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-slate-400 mt-1">
                        {isZh ? '未检测到独立显卡加速设备，将使用 CPU 进行轻量推理' : 'Fallback to CPU execution'}
                      </p>
                    )}
                  </div>
                </div>

                {/* RAM Card */}
                <div className="p-4 rounded-xl bg-slate-800/40 border border-white/[0.06] flex flex-col justify-between">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
                      <Zap className="w-4 h-4 text-purple-400" />
                      {isZh ? '系统内存 (RAM)' : 'System Memory'}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 font-medium border border-purple-500/30">
                      Host RAM
                    </span>
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white">
                      {hardware ? `${totalRamGb} GB RAM` : (isZh ? '正在读取内存...' : 'Reading RAM...')}
                    </div>
                    {hardware ? (
                      <div className="space-y-1.5 mt-2">
                        <div className="flex items-center justify-between text-xs text-slate-300 font-mono">
                          <span>
                            {isZh ? '当前可用' : 'Available'}: <strong className="text-purple-300">{availRamGb} GB</strong>
                          </span>
                          <span className="text-slate-400 text-[11px]">{ramPercent}% {isZh ? '已用' : 'Used'}</span>
                        </div>
                        <div className="w-full h-1.5 rounded-full bg-slate-700/60 overflow-hidden">
                          <div
                            className="h-full bg-purple-500 transition-all duration-300"
                            style={{ width: `${ramPercent}%` }}
                          />
                        </div>
                        <p className="text-[10px] text-slate-400 pt-0.5">
                          {isZh
                            ? totalRamGb >= 16 ? '内存充裕，支持同时加载大模型与绘图管道' : '建议部署轻量模型避免内存超载'
                            : totalRamGb >= 16 ? 'Ample memory for models & workflows' : 'Lightweight model recommended'}
                        </p>
                      </div>
                    ) : (
                      <p className="text-xs text-slate-400 mt-1">
                        {isZh ? '正在从系统内核读取内存状态...' : 'Querying host system RAM...'}
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
                    <span>{isZh ? '磁盘存储空间 (Engine & Model Root)' : 'Disk Storage'}</span>
                  </span>
                  <span className="text-slate-300 font-mono text-xs">
                    {hardware ? (
                      <>
                        <strong className="text-slate-100">{storageFreeGb.toFixed(1)} GB</strong>{' '}
                        {isZh ? '可用' : 'Free'} / {storageTotalGb.toFixed(0)} GB
                      </>
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
                      ? (isZh ? '正在分析系统硬件规格与显卡加速通道...' : 'Evaluating hardware compatibility...')
                      : (isZh ? '请启动后端服务以加载硬件规格' : 'Start backend service to load hardware specs'))}
                </div>
                {hardware?.guidance_notes && hardware.guidance_notes.length > 0 && (
                  <ul className="text-[11px] text-slate-400 space-y-1 list-disc pl-4 pt-1">
                    {hardware.guidance_notes.map((note, idx) => (
                      <li key={idx}>{note}</li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Ollama Service Status Card */}
              <div className="p-4 rounded-xl bg-slate-800/40 border border-white/[0.06] space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="w-9 h-9 rounded-lg bg-slate-800 flex items-center justify-center text-slate-300">
                      <Server className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-white flex items-center gap-2">
                        <span>{isZh ? '内置 Ollama 运行状态' : 'Embedded Ollama Runtime'}</span>
                        {ollamaStatus?.running ? (
                          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                        ) : !ollamaStatus?.installed ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 font-medium">
                            {isZh ? '未安装' : 'Not Installed'}
                          </span>
                        ) : (
                          <span className="w-2 h-2 rounded-full bg-amber-400" />
                        )}
                      </div>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        {ollamaStatus?.running
                          ? (isZh ? `已就绪并监听端口 ${ollamaStatus.port}` : `Active on port ${ollamaStatus.port}`)
                          : !ollamaStatus?.installed
                          ? (isZh ? '未检测到 Ollama 运行环境，需先安装' : 'Ollama runtime not found on host')
                          : (isZh ? '服务尚未运行，点击右侧立即启动' : 'Service is currently stopped')}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    {!ollamaStatus?.installed ? (
                      <>
                        <button
                          onClick={handleInstallOllama}
                          disabled={installingOllama}
                          className="flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-medium rounded-lg transition shadow-sm"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>{installingOllama ? (isZh ? '检查中...' : 'Checking...') : (isZh ? '初始化引擎' : 'Init Engine')}</span>
                        </button>
                        <a
                          href="https://ollama.com/download/windows"
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center space-x-1 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-medium rounded-lg border border-white/10 transition"
                        >
                          <ExternalLink className="w-3 h-3" />
                          <span>{isZh ? '获取引擎' : 'Get Engine'}</span>
                        </a>
                      </>
                    ) : !ollamaStatus?.running ? (
                      <button
                        onClick={handleStartOllama}
                        disabled={loadingOllama}
                        className="flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-medium rounded-lg transition-colors shadow-sm"
                      >
                        <Play className="w-3.5 h-3.5" />
                        <span>{loadingOllama ? (isZh ? '启动中...' : 'Starting...') : (isZh ? '启动服务' : 'Start Service')}</span>
                      </button>
                    ) : (
                      <span className="text-xs text-emerald-400 font-medium flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>{isZh ? '已在线运行' : 'Running'}</span>
                      </span>
                    )}
                  </div>
                </div>

                {installMessage && (
                  <div className="p-2.5 rounded-lg bg-indigo-950/40 border border-indigo-500/20 text-xs text-indigo-200">
                    {installMessage}
                  </div>
                )}

                {startError && (
                  <div className="p-2.5 rounded-lg bg-rose-950/40 border border-rose-500/30 text-xs text-rose-300 flex items-center gap-2">
                    <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                    <span>{startError}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* STEP 2: Deploy Model */}
          {activeStep === 2 && (
            <div className="space-y-4">
              {/* Ollama Not Ready Warning Banner */}
              {ollamaStatus && !ollamaStatus.installed && (
                <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-500/30 text-xs text-amber-200 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                    <span>
                      {isZh
                        ? '注意：未检测到独立 Ollama 引擎。模型部署需嵌入独立执行引擎（无需改变系统环境变量）。'
                        : 'Notice: Embedded Ollama engine not detected. Model deployment requires the isolated engine.'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleInstallOllama}
                      disabled={installingOllama}
                      className="px-2.5 py-1 rounded bg-amber-600 hover:bg-amber-500 text-white font-medium text-[11px] transition shadow"
                    >
                      {installingOllama ? (isZh ? '检查中...' : 'Checking...') : (isZh ? '初始化引擎' : 'Init Engine')}
                    </button>
                    <a
                      href="https://ollama.com/download/windows"
                      target="_blank"
                      rel="noreferrer"
                      className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] transition border border-white/10"
                    >
                      {isZh ? '获取引擎' : 'Get Engine'}
                    </a>
                  </div>
                </div>
              )}

              <div className="p-3 rounded-lg bg-indigo-950/30 border border-indigo-500/20 text-xs text-slate-200 leading-relaxed">
                <span className="text-indigo-300 font-semibold">{isZh ? '硬件适配诊断：' : 'Hardware Telemetry: '}</span>
                <span>
                  {isZh
                    ? `根据您的真实硬件规格（${gpuDescHeadline} / ${ramDescHeadline}），为您智能推荐以下最佳适配大语言模型：`
                    : `Based on your live hardware telemetry (${gpuDescHeadline} / ${ramDescHeadline}), we recommend the following models:`}
                </span>
              </div>

              <div className="space-y-2.5">
                {PRESET_MODELS.map((model) => {
                  const isSelected = selectedModel === model.name;
                  const isAlreadyInstalled = ollamaStatus?.models?.some(
                    (m) => m.name === model.name || m.name.startsWith(model.name.split(':')[0])
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
                            {isZh ? model.labelZh : model.labelEn}
                          </span>
                          {isRecommended && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-medium">
                              {isZh ? '最佳匹配' : 'Optimal'}
                            </span>
                          )}
                          {isAlreadyInstalled && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-medium">
                              {isZh ? '已安装' : 'Installed'}
                            </span>
                          )}
                          {fitsGpu ? (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 font-mono">
                              {isZh ? '显卡满血' : 'GPU Max'}
                            </span>
                          ) : fitsRam ? (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-300 font-mono">
                              {isZh ? '内存混合' : 'RAM Hybrid'}
                            </span>
                          ) : (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-700/40 text-slate-400 font-mono">
                              {isZh ? '较高负载' : 'Heavy Load'}
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-slate-400">
                          {isZh ? model.descZh : model.descEn}
                        </p>
                        <div className="flex items-center gap-3 text-[10px] text-slate-500 pt-0.5">
                          <span>{isZh ? '下载体积' : 'Download Size'}: {model.size}</span>
                          <span>•</span>
                          <span>{isZh ? '显存要求' : 'VRAM req'}: {Math.round(model.vramReqMb / 1024)} GB+</span>
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
                      {pullProgress.status || (isZh ? '正在下载模型分片...' : 'Pulling model...')}
                    </span>
                    <span className="text-white font-mono font-bold">{pullProgress.percent}%</span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-300"
                      style={{ width: `${pullProgress.percent}%` }}
                    />
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
                  {isZh ? '大模型基座与智能体已就绪！' : 'Local Model & Agent Base Ready!'}
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  {isZh
                    ? '您的本地大语言模型现已启动并与 Berry AI Studio 深度集成。您可以在右侧 Agents 面板或创意画布中直接使用自然语言提需求并生成工作流。'
                    : 'Your local LLM is now running seamlessly with Berry AI Studio. Open the right-side Agent sidebar to chat, generate images, or orchestrate workflows.'}
                </p>
              </div>

              {ollamaStatus?.models && ollamaStatus.models.length > 0 && (
                <div className="w-full max-w-sm p-3 rounded-xl bg-slate-800/40 border border-white/[0.06] text-left text-xs">
                  <div className="font-semibold text-slate-300 mb-1">
                    {isZh ? '已加载本地模型清单:' : 'Loaded Local Models:'}
                  </div>
                  <div className="space-y-1">
                    {ollamaStatus.models.map((m) => (
                      <div key={m.name} className="flex justify-between text-slate-400 font-mono text-[11px]">
                        <span>• {m.name}</span>
                        <span>{Math.round((m.size_bytes / (1024 * 1024 * 1024)) * 10) / 10} GB</span>
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
                onClick={() => setActiveStep((prev) => (prev - 1) as any)}
                disabled={isPulling}
                className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white transition-colors"
              >
                {isZh ? '返回上一步' : 'Back'}
              </button>
            )}
          </div>

          <div className="flex items-center space-x-2.5">
            {activeStep === 1 && (
              <button
                onClick={() => setActiveStep(2)}
                className="flex items-center space-x-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-600/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
              >
                <span>{isZh ? '下一步：选择并部署模型' : 'Next: Select & Deploy'}</span>
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
                    ? (isZh ? '正在拉取模型...' : 'Pulling Model...')
                    : (isZh ? `立即下载并部署 ${selectedModel}` : `Deploy ${selectedModel}`)}
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
                <span>{isZh ? '立即进入 AI Agent 创作' : 'Open AI Agent Now'}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
