import React from 'react';
import { Settings, Cpu, Globe, Info } from 'lucide-react';

interface SettingsViewProps {
  onOpenCloudSettings?: () => void;
  onOpenEnvironmentManager?: () => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  onOpenCloudSettings,
  onOpenEnvironmentManager,
}) => {
  return (
    <div className="flex flex-col w-full h-full overflow-y-auto bg-slate-950 text-slate-100 p-8 select-none">
      <div className="max-w-3xl mx-auto w-full">
        {/* Header */}
        <div className="flex items-center space-x-3 mb-8 pb-4 border-b border-white/[0.08]">
          <div className="w-10 h-10 rounded-xl bg-slate-900 border border-white/[0.08] flex items-center justify-center text-indigo-400">
            <Settings className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">System Settings</h1>
            <p className="text-xs text-slate-400">Configure client behavior, cloud keys, and engine environments.</p>
          </div>
        </div>

        {/* Settings Sections */}
        <div className="space-y-6">
          {/* Cloud & BYOK Settings */}
          <section className="p-5 rounded-2xl bg-slate-900/60 border border-white/[0.08]">
            <div className="flex items-center justify-between">
              <div className="flex items-start space-x-3">
                <Globe className="w-5 h-5 text-indigo-400 mt-0.5" />
                <div>
                  <h2 className="text-sm font-semibold text-slate-100">Cloud API & BYOK Providers</h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Configure API keys for Fal.ai, SiliconFlow, or OpenAI to generate without local GPU requirements.
                  </p>
                </div>
              </div>
              {onOpenCloudSettings && (
                <button
                  onClick={onOpenCloudSettings}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 rounded-lg border border-slate-700 transition-colors"
                >
                  Configure Keys
                </button>
              )}
            </div>
          </section>

          {/* Environment & Model Manager */}
          <section className="p-5 rounded-2xl bg-slate-900/60 border border-white/[0.08]">
            <div className="flex items-center justify-between">
              <div className="flex items-start space-x-3">
                <Cpu className="w-5 h-5 text-indigo-400 mt-0.5" />
                <div>
                  <h2 className="text-sm font-semibold text-slate-100">Local Engines & Model Catalog</h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Manage ComfyUI and WebUI installation paths, scan model directories, and inspect hardware.
                  </p>
                </div>
              </div>
              {onOpenEnvironmentManager && (
                <button
                  onClick={onOpenEnvironmentManager}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 rounded-lg border border-slate-700 transition-colors"
                >
                  Manage Environments
                </button>
              )}
            </div>
          </section>

          {/* About & System Info */}
          <section className="p-5 rounded-2xl bg-slate-900/40 border border-white/[0.06] text-xs text-slate-400 space-y-2">
            <div className="flex items-center space-x-2 text-slate-300 font-semibold mb-1">
              <Info className="w-4 h-4 text-indigo-400" />
              <span>Berry AI Studio v0.1.0</span>
            </div>
            <p>Unified multimodal creation workspace powered by FastAPI, React 18, and Tauri v2.</p>
            <p className="font-mono text-[11px] text-slate-500">Zero Host Pollution · 5-Type Port Contract · API-First Architecture</p>
          </section>
        </div>
      </div>
    </div>
  );
};
