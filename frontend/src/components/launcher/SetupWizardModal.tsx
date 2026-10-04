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
} from 'lucide-react';
import { useSettingsStore } from '../../stores/useSettingsStore';

interface HardwareInfo {
  has_nvidia_gpu: boolean;
  has_discrete_gpu: boolean;
  gpu_vendor: string;
  acceleration_backend: string;
  gpus: Array<{
    name: string;
    vram_total_mb: number;
    vram_free_mb: number;
  }>;
  ram_total_mb: number;
  ram_avail_mb: number;
  engine_storage?: {
    total_gb: number;
    free_gb: number;
    is_sufficient: boolean;
  };
  recommended_engine?: string;
  summary_message: string;
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

const PRESET_MODELS = [
  {
    name: 'qwen2.5:7b',
    label: 'Qwen 2.5 (7B) - 综合推荐',
    size: '4.7 GB',
    vramReq: '6 GB+ 显存',
    desc: '阿里千问最新高智商模型，完美支持多语言创意扩写与工作流编排',
    recommended: true,
  },
  {
    name: 'deepseek-r1:8b',
    label: 'DeepSeek R1 (8B) - 深度推理',
    size: '4.9 GB',
    vramReq: '8 GB+ 显存',
    desc: '深度强化学习推理模型，长思考链路，擅长复杂提示词逻辑设计',
    recommended: false,
  },
  {
    name: 'llama3.2:3b',
    label: 'Llama 3.2 (3B) - 轻量极速',
    size: '2.0 GB',
    vramReq: '3 GB+ 显存',
    desc: 'Meta 推出超轻量高效模型，启动迅捷，可在低显存或CPU流畅运行',
    recommended: false,
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
  const [ollamaStatus, setOllamaStatus] = useState<OllamaStatus | null>(null);
  const [loadingOllama, setLoadingOllama] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>('qwen2.5:7b');
  const [isPulling, setIsPulling] = useState(false);
  const [pullProgress, setPullProgress] = useState<{ status: string; percent: number }>({
    status: '',
    percent: 0,
  });
  const [pullError, setPullError] = useState<string | null>(null);

  const fetchDiagnostics = async () => {
    setLoadingOllama(true);
    try {
      const hwRes = await fetch('/api/v1/hardware/readiness');
      if (hwRes.ok) {
        const hwData = await hwRes.json();
        setHardware(hwData);
      }
    } catch (e) {
      console.warn('Failed to fetch hardware readiness:', e);
    }

    try {
      const olRes = await fetch('/api/v1/ollama/status');
      if (olRes.ok) {
        const olData = await olRes.json();
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
    try {
      await fetch('/api/v1/ollama/start', { method: 'POST' });
      await fetchDiagnostics();
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingOllama(false);
    }
  };

  const handlePullModel = async (modelName: string) => {
    setIsPulling(true);
    setPullError(null);
    setPullProgress({ status: isZh ? '正在建立连接...' : 'Connecting...', percent: 0 });

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
              setPullError(data.error);
              setIsPulling(false);
              return;
            }
            const status = data.status || '';
            const total = data.total || 0;
            const completed = data.completed || 0;
            const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
            setPullProgress({ status, percent: pct });
          } catch {
            // ignore JSON parse error in chunk
          }
        }
      }

      // Completed successfully
      setIsPulling(false);
      await fetchDiagnostics();
      setActiveStep(3);
    } catch (err: any) {
      setPullError(err?.message || 'Download failed');
      setIsPulling(false);
    }
  };

  const primaryGpu = hardware?.gpus?.[0];

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
                  ? '一站式检测硬件配置、管理内置 Ollama 服务与极速部署本地大模型'
                  : 'Automatic GPU diagnosis, embedded Ollama lifecycle & instant local model provisioning'}
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
            <span>{isZh ? '2. 本地模型部署' : '2. Deploy Model'}</span>
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
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* GPU Card */}
                <div className="p-4 rounded-xl bg-slate-800/40 border border-white/[0.06] flex flex-col justify-between">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
                      <Cpu className="w-4 h-4 text-indigo-400" />
                      {isZh ? '图形显卡 (GPU)' : 'Graphics Processor'}
                    </span>
                    {hardware?.has_nvidia_gpu ? (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-medium">
                        NVIDIA CUDA
                      </span>
                    ) : (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-medium">
                        {hardware?.gpu_vendor.toUpperCase() || 'CPU'}
                      </span>
                    )}
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white truncate">
                      {primaryGpu?.name || (isZh ? '未检测到独立显卡' : 'No Dedicated GPU')}
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                      {primaryGpu ? (
                        <>
                          {isZh ? '显存容量' : 'VRAM'}:{' '}
                          <span className="text-indigo-300 font-semibold">
                            {Math.round(primaryGpu.vram_total_mb / 1024)} GB
                          </span>{' '}
                          ({isZh ? '剩余可用' : 'Free'}: {Math.round(primaryGpu.vram_free_mb / 1024)} GB)
                        </>
                      ) : (
                        isZh ? '将使用 CPU 执行模型推理' : 'Fallback to CPU execution'
                      )}
                    </div>
                  </div>
                </div>

                {/* RAM Card */}
                <div className="p-4 rounded-xl bg-slate-800/40 border border-white/[0.06] flex flex-col justify-between">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
                      <Zap className="w-4 h-4 text-purple-400" />
                      {isZh ? '系统内存 (RAM)' : 'System Memory'}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 font-medium">
                      Host RAM
                    </span>
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white">
                      {hardware ? Math.round(hardware.ram_total_mb / 1024) : 16} GB RAM
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                      {isZh ? '可用内存' : 'Available'}:{' '}
                      <span className="text-purple-300 font-semibold">
                        {hardware ? Math.round(hardware.ram_avail_mb / 1024) : 8} GB
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Storage & Readiness Banner */}
              <div className="p-4 rounded-xl bg-slate-800/20 border border-white/[0.06] space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400 flex items-center gap-1.5">
                    <HardDrive className="w-3.5 h-3.5 text-slate-400" />
                    {isZh ? '磁盘存储空间 (Engine Root)' : 'Disk Storage'}
                  </span>
                  <span className="text-slate-300 font-mono">
                    {hardware?.engine_storage?.free_gb || 0} GB Free
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-indigo-950/40 border border-indigo-500/20 text-xs text-indigo-200 leading-relaxed">
                  {hardware?.summary_message ||
                    (isZh ? '正在分析系统硬件规格...' : 'Evaluating hardware compatibility...')}
                </div>
              </div>

              {/* Ollama Service Status Card */}
              <div className="p-4 rounded-xl bg-slate-800/40 border border-white/[0.06] flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-9 h-9 rounded-lg bg-slate-800 flex items-center justify-center text-slate-300">
                    <Server className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-white flex items-center gap-2">
                      <span>{isZh ? '内置 Ollama 服务状态' : 'Embedded Ollama Runtime'}</span>
                      {ollamaStatus?.running ? (
                        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                      ) : (
                        <span className="w-2 h-2 rounded-full bg-amber-400" />
                      )}
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      {ollamaStatus?.running
                        ? (isZh ? `已在端口 ${ollamaStatus.port} 就绪` : `Active on port ${ollamaStatus.port}`)
                        : (isZh ? '服务尚未运行，点击启动' : 'Service is currently stopped')}
                    </p>
                  </div>
                </div>

                {!ollamaStatus?.running ? (
                  <button
                    onClick={handleStartOllama}
                    disabled={loadingOllama}
                    className="flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium rounded-lg transition-colors shadow-sm"
                  >
                    <Play className="w-3.5 h-3.5" />
                    <span>{isZh ? '启动服务' : 'Start Service'}</span>
                  </button>
                ) : (
                  <span className="text-xs text-emerald-400 font-medium flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    {isZh ? '运行中' : 'Running'}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* STEP 2: Deploy Model */}
          {activeStep === 2 && (
            <div className="space-y-4">
              <p className="text-xs text-slate-300">
                {isZh
                  ? '根据您的硬件规格（RTX 4060 Ti 16GB / 系统内存），我们为您推荐以下兼容大语言模型：'
                  : 'Based on your hardware evaluation, select an optimized model to pull into local Ollama:'}
              </p>

              <div className="space-y-2.5">
                {PRESET_MODELS.map((model) => {
                  const isSelected = selectedModel === model.name;
                  const isAlreadyInstalled = ollamaStatus?.models?.some(
                    (m) => m.name === model.name || m.name.startsWith(model.name.split(':')[0])
                  );

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
                          <span className="text-xs font-bold text-white">{model.label}</span>
                          {model.recommended && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-medium">
                              {isZh ? '最佳匹配' : 'Optimal'}
                            </span>
                          )}
                          {isAlreadyInstalled && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-medium">
                              {isZh ? '已安装' : 'Installed'}
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-slate-400">{model.desc}</p>
                        <div className="flex items-center gap-3 text-[10px] text-slate-500 pt-0.5">
                          <span>{isZh ? '下载体积' : 'Download Size'}: {model.size}</span>
                          <span>•</span>
                          <span>{isZh ? '显存要求' : 'VRAM req'}: {model.vramReq}</span>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2 shrink-0">
                        {isAlreadyInstalled ? (
                          <span className="text-xs text-emerald-400 font-medium flex items-center gap-1">
                            <CheckCircle2 className="w-4 h-4" />
                          </span>
                        ) : (
                          <div
                            className={`w-4 h-4 rounded-full border flex items-center justify-center ${
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
                        <span>{Math.round(m.size_bytes / (1024 * 1024 * 1024) * 10) / 10} GB</span>
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
