import React from 'react';
import { Download, AlertCircle, FolderSearch, X, Sparkles, CheckCircle2 } from 'lucide-react';
import { EngineInstance } from '../../stores/useEngineStore';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { t } from '../../i18n/translations';

interface EngineNotInstalledModalProps {
  isOpen: boolean;
  instance: EngineInstance | null;
  errorMessage?: string | null;
  onClose: () => void;
  onDeploy: (engineType: 'comfyui' | 'webui') => void;
  onLocate: (engineType: 'comfyui' | 'webui') => void;
}

export const EngineNotInstalledModal: React.FC<EngineNotInstalledModalProps> = ({
  isOpen,
  instance,
  errorMessage,
  onClose,
  onDeploy,
  onLocate,
}) => {
  const { getEffectiveLanguage } = useSettingsStore();
  const lang = getEffectiveLanguage();

  if (!isOpen || !instance) return null;

  const engineType = (instance.type === 'webui' ? 'webui' : 'comfyui') as 'comfyui' | 'webui';
  const engineTitle = instance.name || (engineType === 'comfyui' ? 'ComfyUI' : 'SD WebUI');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm select-none animate-in fade-in duration-150">
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden p-6 text-slate-100 animate-in zoom-in-95 duration-150">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          title="Close"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Header with Icon */}
        <div className="flex items-center gap-3.5 mb-4">
          <div className="w-11 h-11 rounded-xl bg-amber-500/10 border border-amber-500/25 flex items-center justify-center text-amber-400 shrink-0">
            <AlertCircle className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">
              {engineTitle} {t('engine_not_installed_title', lang) || 'is Not Installed'}
            </h2>
            <p className="text-xs text-slate-400">
              {t('engine_not_installed_subtitle', lang) || 'Sandboxed runtime environment was not detected'}
            </p>
          </div>
        </div>

        {/* Informative Explanation */}
        <div className="space-y-3 mb-5">
          <p className="text-xs text-slate-300 leading-relaxed">
            {t('engine_not_installed_desc', lang) ||
              `To maintain zero host pollution, Berry AI Studio requires an isolated runtime environment before ${engineTitle} can be started.`}
          </p>

          {errorMessage && (
            <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 text-[11px] font-mono text-amber-300/90 break-words">
              {errorMessage}
            </div>
          )}

          {/* Value Props / Highlights */}
          <div className="grid grid-cols-2 gap-2 pt-1">
            <div className="flex items-center space-x-2 p-2 rounded-lg bg-slate-800/40 border border-white/[0.04] text-[11px] text-slate-300">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span>{t('engine_benefit_isolated', lang) || '100% Isolated Venv'}</span>
            </div>
            <div className="flex items-center space-x-2 p-2 rounded-lg bg-slate-800/40 border border-white/[0.04] text-[11px] text-slate-300">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
              <span>{t('engine_benefit_mirrors', lang) || 'Accelerated Mirrors'}</span>
            </div>
          </div>
        </div>

        {/* Action Options */}
        <div className="flex flex-col sm:flex-row gap-2.5 pt-2 border-t border-slate-800">
          <button
            onClick={() => {
              onClose();
              onDeploy(engineType);
            }}
            className="flex-1 flex items-center justify-center space-x-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-600/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
          >
            <Download className="w-4 h-4" />
            <span>{t('btn_deploy_now', lang) || 'Deploy & Install Now'}</span>
          </button>

          <button
            onClick={() => {
              onClose();
              onLocate(engineType);
            }}
            className="flex-1 flex items-center justify-center space-x-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-xs rounded-xl border border-slate-700 transition-colors"
          >
            <FolderSearch className="w-4 h-4 text-slate-400" />
            <span>{t('btn_locate_existing', lang) || 'Locate Existing Folder'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
