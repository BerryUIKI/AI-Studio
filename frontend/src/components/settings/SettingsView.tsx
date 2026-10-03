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

type SettingsSection = 'general' | 'startup' | 'exit' | 'cloud' | 'engines' | 'about';

export const SettingsView: React.FC<SettingsViewProps> = ({
  onOpenCloudSettings,
  onOpenEnvironmentManager,
}) => {
  const [activeSection, setActiveSection] = useState<SettingsSection>('general');

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
