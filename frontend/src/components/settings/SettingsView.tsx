import React, { useState } from 'react';
import {
  Settings,
  Languages,
  Compass,
  Power,
  Globe,
  Cpu,
  Info,
  ChevronRight,
  Check,
  Bot,
  Loader2,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import {
  useSettingsStore,
  ExitPolicy,
  DefaultLandingView,
} from '../../stores/useSettingsStore';
import {
  LANGUAGE_OPTIONS,
  LanguageSetting,
  t,
  resolveEffectiveLanguage,
} from '../../i18n/translations';

interface SettingsViewProps {
  onOpenCloudSettings?: () => void;
  onOpenEnvironmentManager?: () => void;
}

type SettingsSection = 'general' | 'agent' | 'startup' | 'exit' | 'cloud' | 'engines' | 'about';

export const SettingsView: React.FC<SettingsViewProps> = ({
  onOpenCloudSettings,
  onOpenEnvironmentManager,
}) => {
  const [activeSection, setActiveSection] = useState<SettingsSection>('general');

  // LLM Config state
  const [llmConfig, setLlmConfig] = useState({
    provider: 'ollama',
    model: 'qwen2.5:7b',
    base_url: 'http://127.0.0.1:11434/v1',
    api_key: '',
    temperature: 0.7,
    enabled: true,
  });
  const [llmTesting, setLlmTesting] = useState(false);
  const [llmTestResult, setLlmTestResult] = useState<{ valid: boolean; message: string } | null>(null);
  const [llmSaving, setLlmSaving] = useState(false);

  React.useEffect(() => {
    fetch('/api/v1/agent/llm/config')
      .then((res) => res.json())
      .then((data) => {
        if (data && data.provider) setLlmConfig(data);
      })
      .catch(() => {});
  }, []);

  const handleSaveLlmConfig = async () => {
    setLlmSaving(true);
    try {
      const res = await fetch('/api/v1/agent/llm/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(llmConfig),
      });
      if (res.ok) {
        setLlmTestResult({ valid: true, message: 'Settings saved successfully!' });
      }
    } finally {
      setLlmSaving(false);
    }
  };

  const handleTestLlmConnection = async () => {
    setLlmTesting(true);
    setLlmTestResult(null);
    try {
      const res = await fetch('/api/v1/agent/llm/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(llmConfig),
      });
      const data = await res.json();
      setLlmTestResult({ valid: data.valid, message: data.message });
    } catch (err: any) {
      setLlmTestResult({ valid: false, message: err.message || 'Connection failed' });
    } finally {
      setLlmTesting(false);
    }
  };

  const {
    language,
    setLanguage,
    exitPolicy,
    setExitPolicy,
    defaultLandingView,
    setDefaultLandingView,
  } = useSettingsStore();

  const currentLang = resolveEffectiveLanguage(language);

  const sections: { id: SettingsSection; label: string; icon: React.ElementType }[] = [
    { id: 'general', label: t('tab_general', currentLang), icon: Languages },
    { id: 'agent', label: 'AI Agent & LLM (大模型基座)', icon: Bot },
    { id: 'startup', label: t('tab_startup', currentLang), icon: Compass },
    { id: 'exit', label: t('tab_exit', currentLang), icon: Power },
    { id: 'cloud', label: t('tab_cloud', currentLang), icon: Globe },
    { id: 'engines', label: t('tab_engines', currentLang), icon: Cpu },
    { id: 'about', label: t('tab_about', currentLang), icon: Info },
  ];

  return (
    <div className="flex w-full h-full bg-slate-950 text-slate-100 select-none overflow-hidden">
      {/* Left Dedicated Settings Navigation Sidebar */}
      <aside className="w-64 border-r border-white/[0.08] bg-slate-900/40 p-4 flex flex-col justify-between shrink-0">
        <div className="space-y-6">
          {/* Header */}
          <div className="flex items-center space-x-3 px-2 pt-2">
            <div className="w-9 h-9 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shadow-inner">
              <Settings className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-base font-bold text-white tracking-tight">
                {t('settings_title', currentLang)}
              </h1>
              <p className="text-[11px] text-slate-400 truncate">Berry AI Studio</p>
            </div>
          </div>

          {/* Module Nav Items */}
          <nav className="space-y-1">
            {sections.map((sec) => {
              const Icon = sec.icon;
              const isActive = activeSection === sec.id;
              return (
                <button
                  key={sec.id}
                  onClick={() => setActiveSection(sec.id)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20 font-semibold'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                  }`}
                >
                  <div className="flex items-center space-x-2.5">
                    <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                    <span>{sec.label}</span>
                  </div>
                  <ChevronRight
                    className={`w-3.5 h-3.5 transition-transform ${
                      isActive ? 'text-white/80 translate-x-0.5' : 'text-slate-600'
                    }`}
                  />
                </button>
              );
            })}
          </nav>
        </div>

        {/* Footer info in sidebar */}
        <div className="px-2 py-3 border-t border-white/[0.06] text-[11px] text-slate-500">
          <span>v0.1.0 · Multi-Platform</span>
        </div>
      </aside>

      {/* Main Settings Content Area */}
      <main className="flex-1 overflow-y-auto p-8 lg:p-10">
        <div className="max-w-3xl mx-auto space-y-6">
          {/* Section: General & Language */}
          {activeSection === 'general' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-bold text-white">{t('lang_heading', currentLang)}</h2>
                <p className="text-xs text-slate-400 mt-0.5">{t('lang_desc', currentLang)}</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {LANGUAGE_OPTIONS.map((opt) => {
                  const isSelected = language === opt.id;
                  return (
                    <div
                      key={opt.id}
                      onClick={() => setLanguage(opt.id as LanguageSetting)}
                      className={`p-3.5 rounded-2xl border cursor-pointer transition-all flex flex-col justify-between min-h-[76px] ${
                        isSelected
                          ? 'bg-indigo-600/15 border-indigo-500/50 shadow-sm shadow-indigo-500/10'
                          : 'bg-slate-900/60 border-slate-800/80 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-200">
                          {opt.nativeLabel}
                        </span>
                        {isSelected && <Check className="w-4 h-4 text-indigo-400 shrink-0" />}
                      </div>
                      <span className="text-[11px] text-slate-400">{opt.label}</span>
                    </div>
                  );
                })}
              </div>

              {language === 'system' && (
                <div className="p-3 rounded-xl bg-slate-900/40 border border-white/[0.06] text-xs text-slate-400 flex items-center justify-between">
                  <span>{t('lang_system_detected', currentLang)}:</span>
                  <span className="font-mono text-indigo-300 uppercase font-semibold">
                    {currentLang}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Section: AI Agent & LLM Base (Priority Localized) */}
          {activeSection === 'agent' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <Bot className="w-5 h-5 text-indigo-400" />
                  <span>AI Agent 推理基座与大模型配置 (LLM Base)</span>
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  为右侧常驻 AI Agents 赋予真正的大语言模型推理与自主规划能力，优先支持本地私有化部署（Ollama / vLLM / LocalAI），亦支持云端商用模型。
                </p>
              </div>

              {/* Provider Selection */}
              <div className="p-5 rounded-2xl bg-slate-900/60 border border-white/[0.08] space-y-4">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-200">基座供应商类型 (Provider)</label>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-slate-400">启用智能 Agent 推理</span>
                    <input
                      type="checkbox"
                      checked={llmConfig.enabled}
                      onChange={(e) => setLlmConfig({ ...llmConfig, enabled: e.target.checked })}
                      className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 bg-slate-800 border-slate-700"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  {[
                    { id: 'ollama', label: 'Local Ollama (推荐本地)', desc: '100% 本地运行 · 零 API 费用' },
                    { id: 'siliconflow', label: '硅基流动 (SiliconFlow)', desc: 'Qwen2.5 / DeepSeek 极速 API' },
                    { id: 'deepseek', label: 'DeepSeek 官方', desc: 'DeepSeek-V3 / R1 推理' },
                    { id: 'openai', label: 'OpenAI / Custom', desc: 'GPT-4o 或自定义端点' },
                  ].map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => {
                        let newUrl = llmConfig.base_url;
                        let newModel = llmConfig.model;
                        if (p.id === 'ollama') {
                          newUrl = 'http://127.0.0.1:11434/v1';
                          newModel = 'qwen2.5:7b';
                        } else if (p.id === 'siliconflow') {
                          newUrl = 'https://api.siliconflow.cn/v1';
                          newModel = 'Qwen/Qwen2.5-7B-Instruct';
                        } else if (p.id === 'deepseek') {
                          newUrl = 'https://api.deepseek.com/v1';
                          newModel = 'deepseek-chat';
                        } else if (p.id === 'openai') {
                          newUrl = 'https://api.openai.com/v1';
                          newModel = 'gpt-4o-mini';
                        }
                        setLlmConfig({
                          ...llmConfig,
                          provider: p.id,
                          base_url: newUrl,
                          model: newModel,
                        });
                      }}
                      className={`p-3 rounded-xl border text-left transition-all ${
                        llmConfig.provider === p.id
                          ? 'bg-indigo-600/15 border-indigo-500/50 shadow-sm shadow-indigo-500/10'
                          : 'bg-slate-900/60 border-slate-800/80 hover:border-slate-700'
                      }`}
                    >
                      <span className="text-xs font-semibold text-slate-200 block">{p.label}</span>
                      <span className="text-[10px] text-slate-400 mt-1 block">{p.desc}</span>
                    </button>
                  ))}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                  <div>
                    <label className="text-[11px] font-medium text-slate-300 block mb-1">
                      API Base URL
                    </label>
                    <input
                      type="text"
                      value={llmConfig.base_url}
                      onChange={(e) => setLlmConfig({ ...llmConfig, base_url: e.target.value })}
                      placeholder="e.g. http://127.0.0.1:11434/v1"
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="text-[11px] font-medium text-slate-300 block mb-1">
                      模型标识 (Model Identifier)
                    </label>
                    <input
                      type="text"
                      value={llmConfig.model}
                      onChange={(e) => setLlmConfig({ ...llmConfig, model: e.target.value })}
                      placeholder="e.g. qwen2.5:7b, deepseek-r1:8b"
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div className="sm:col-span-2">
                    <label className="text-[11px] font-medium text-slate-300 block mb-1">
                      API Key (本地 Ollama 可留空)
                    </label>
                    <input
                      type="password"
                      value={llmConfig.api_key || ''}
                      onChange={(e) => setLlmConfig({ ...llmConfig, api_key: e.target.value })}
                      placeholder={llmConfig.provider === 'ollama' ? '本地运行无需 API Key' : 'sk-...'}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                </div>

                {/* Test Feedback */}
                {llmTestResult && (
                  <div
                    className={`p-3 rounded-xl text-xs flex items-center gap-2 ${
                      llmTestResult.valid
                        ? 'bg-emerald-950/40 text-emerald-300 border border-emerald-800/40'
                        : 'bg-rose-950/40 text-rose-300 border border-rose-800/40'
                    }`}
                  >
                    {llmTestResult.valid ? (
                      <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
                    ) : (
                      <XCircle className="w-4 h-4 shrink-0 text-rose-400" />
                    )}
                    <span>{llmTestResult.message}</span>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex items-center gap-3 pt-2">
                  <button
                    type="button"
                    onClick={handleTestLlmConnection}
                    disabled={llmTesting}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 text-xs font-semibold rounded-xl border border-slate-700 transition flex items-center gap-1.5"
                  >
                    {llmTesting && <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />}
                    <span>测试连通性 (Test Connection)</span>
                  </button>

                  <button
                    type="button"
                    onClick={handleSaveLlmConfig}
                    disabled={llmSaving}
                    className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-md shadow-indigo-600/20 transition flex items-center gap-1.5"
                  >
                    {llmSaving ? '保存中...' : '保存配置 (Save Configuration)'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Section: Startup & Landing */}
          {activeSection === 'startup' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-bold text-white">{t('startup_heading', currentLang)}</h2>
                <p className="text-xs text-slate-400 mt-0.5">{t('startup_desc', currentLang)}</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[
                  {
                    id: 'launcher' as DefaultLandingView,
                    title: t('startup_launcher', currentLang),
                    desc: t('startup_launcher_desc', currentLang),
                  },
                  {
                    id: 'canvas' as DefaultLandingView,
                    title: t('startup_canvas', currentLang),
                    desc: t('startup_canvas_desc', currentLang),
                  },
                ].map((opt) => (
                  <div
                    key={opt.id}
                    onClick={() => setDefaultLandingView(opt.id)}
                    className={`p-4 rounded-2xl border cursor-pointer transition-all ${
                      defaultLandingView === opt.id
                        ? 'bg-indigo-600/15 border-indigo-500/50 shadow-sm shadow-indigo-500/10'
                        : 'bg-slate-900/60 border-slate-800/80 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-semibold text-slate-200">{opt.title}</span>
                      <span
                        className={`w-2 h-2 rounded-full ${
                          defaultLandingView === opt.id ? 'bg-indigo-400' : 'bg-slate-700'
                        }`}
                      />
                    </div>
                    <p className="text-[11px] text-slate-400 leading-relaxed">{opt.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section: Exit Policy */}
          {activeSection === 'exit' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-bold text-white">{t('exit_heading', currentLang)}</h2>
                <p className="text-xs text-slate-400 mt-0.5">{t('exit_desc', currentLang)}</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {[
                  {
                    id: 'prompt' as ExitPolicy,
                    title: t('exit_prompt', currentLang),
                    desc: t('exit_prompt_desc', currentLang),
                  },
                  {
                    id: 'close_all' as ExitPolicy,
                    title: t('exit_close_all', currentLang),
                    desc: t('exit_close_all_desc', currentLang),
                  },
                  {
                    id: 'keep_running' as ExitPolicy,
                    title: t('exit_keep_running', currentLang),
                    desc: t('exit_keep_running_desc', currentLang),
                  },
                ].map((opt) => (
                  <div
                    key={opt.id}
                    onClick={() => setExitPolicy(opt.id)}
                    className={`p-4 rounded-2xl border cursor-pointer transition-all ${
                      exitPolicy === opt.id
                        ? 'bg-rose-600/15 border-rose-500/50 shadow-sm shadow-rose-500/10'
                        : 'bg-slate-900/60 border-slate-800/80 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-semibold text-slate-200">{opt.title}</span>
                      <span
                        className={`w-2 h-2 rounded-full ${
                          exitPolicy === opt.id ? 'bg-rose-400' : 'bg-slate-700'
                        }`}
                      />
                    </div>
                    <p className="text-[11px] text-slate-400 leading-relaxed">{opt.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section: Cloud BYOK */}
          {activeSection === 'cloud' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-bold text-white">{t('cloud_heading', currentLang)}</h2>
                <p className="text-xs text-slate-400 mt-0.5">{t('cloud_desc', currentLang)}</p>
              </div>

              <div className="p-6 rounded-2xl bg-slate-900/60 border border-white/[0.08] flex items-center justify-between">
                <div>
                  <h3 className="text-xs font-semibold text-slate-200">
                    OpenAI · Fal.ai · SiliconFlow
                  </h3>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Store API tokens securely on this device without leaking to cloud logs.
                  </p>
                </div>
                {onOpenCloudSettings && (
                  <button
                    onClick={onOpenCloudSettings}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white rounded-xl shadow-md shadow-indigo-600/20 transition-all shrink-0 ml-4"
                  >
                    {t('cloud_btn', currentLang)}
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Section: Engines & Hardware */}
          {activeSection === 'engines' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-bold text-white">{t('engines_heading', currentLang)}</h2>
                <p className="text-xs text-slate-400 mt-0.5">{t('engines_desc', currentLang)}</p>
              </div>

              <div className="p-6 rounded-2xl bg-slate-900/60 border border-white/[0.08] flex items-center justify-between">
                <div>
                  <h3 className="text-xs font-semibold text-slate-200">
                    ComfyUI & Stable Diffusion WebUI
                  </h3>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Manage isolated engine virtualenvs, model search roots, and GPU device assignments.
                  </p>
                </div>
                {onOpenEnvironmentManager && (
                  <button
                    onClick={onOpenEnvironmentManager}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white rounded-xl shadow-md shadow-indigo-600/20 transition-all shrink-0 ml-4"
                  >
                    {t('engines_btn', currentLang)}
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Section: About */}
          {activeSection === 'about' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-bold text-white">{t('about_heading', currentLang)}</h2>
                <p className="text-xs text-slate-400 mt-0.5">{t('about_desc', currentLang)}</p>
              </div>

              <div className="p-6 rounded-2xl bg-slate-900/60 border border-white/[0.08] space-y-3">
                <div className="flex items-center space-x-2 text-indigo-400 text-xs font-bold uppercase tracking-wider">
                  <Info className="w-4 h-4" />
                  <span>Berry AI Studio v0.1.0</span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  A high-performance creative studio for generative AI, blending cloud flexibility with optional zero-host-pollution local execution.
                </p>
                <div className="pt-2 border-t border-white/[0.06]">
                  <p className="font-mono text-[11px] text-slate-400">
                    {t('about_manifesto', currentLang)}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};
