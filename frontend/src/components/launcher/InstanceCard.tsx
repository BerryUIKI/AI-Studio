import React, { useState, useRef, useEffect } from 'react';
import {
  Palette,
  Puzzle,
  Image as ImageIcon,
  Bot,
  Cpu,
  MoreVertical,
  Play,
  Square,
  Settings,
  FileText,
  FolderOpen,
  Trash2,
  ExternalLink,
  Download,
} from 'lucide-react';
import { EngineInstance, StartEngineResult } from '../../stores/useEngineStore';
import { useNavigationStore, ViewType } from '../../stores/useNavigationStore';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { t } from '../../i18n/translations';

interface InstanceCardProps {
  instance: EngineInstance;
  onStart?: (id: string) => Promise<StartEngineResult | boolean> | void;
  onStop?: (id: string) => Promise<boolean> | void;
  onConfigure?: (instance: EngineInstance) => void;
  onViewLogs?: (instance: EngineInstance) => void;
  onOpenDirectory?: (instance: EngineInstance) => void;
  onUninstall?: (instance: EngineInstance) => void;
  onOpenAgent?: () => void;
  onDeploy?: (instance: EngineInstance) => void;
  onLaunchFailed?: (instance: EngineInstance, error: string) => void;
}

export const InstanceCard: React.FC<InstanceCardProps> = ({
  instance,
  onStart,
  onStop,
  onConfigure,
  onViewLogs,
  onOpenDirectory,
  onUninstall,
  onOpenAgent,
  onDeploy,
  onLaunchFailed,
}) => {
  const { setActiveView } = useNavigationStore();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isActing, setIsActing] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  // Close menu on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsMenuOpen(false);
      }
    };
    if (isMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isMenuOpen]);

  const getIcon = () => {
    switch (instance.type) {
      case 'canvas':
        return Palette;
      case 'comfyui':
        return Puzzle;
      case 'webui':
        return ImageIcon;
      case 'agents':
        return Bot;
      default:
        return Cpu;
    }
  };

  const { getEffectiveLanguage } = useSettingsStore();
  const lang = getEffectiveLanguage();
  const Icon = getIcon();
  const isRunning = instance.status === 'running';
  const isReady = instance.status === 'ready';
  const isNotInstalled = instance.status === 'not_installed';

  const handleCardClick = (e: React.MouseEvent) => {
    // If click originated from the context menu or action buttons, don't trigger default
    if ((e.target as HTMLElement).closest('[data-stop-propagation]')) {
      return;
    }

    if (instance.is_builtin) {
      if (instance.type === 'canvas') setActiveView('canvas');
      else if (instance.type === 'agents') onOpenAgent?.();
      return;
    }

    if (isRunning) {
      if (instance.type === 'comfyui') setActiveView('comfyui');
      else if (instance.type === 'webui') setActiveView('webui');
    } else if (isNotInstalled) {
      if (onDeploy) {
        onDeploy(instance);
      }
    } else if (onStart) {
      handleStart();
    }
  };

  const handleStart = async () => {
    if (isNotInstalled) {
      if (onDeploy) onDeploy(instance);
      return;
    }

    if (!onStart) return;
    setIsActing(true);
    try {
      const result = await onStart(instance.id);
      if (result && typeof result === 'object' && !result.success) {
        if (result.code === 'NOT_INSTALLED' || result.code === 'ENV_MISSING') {
          if (onLaunchFailed) {
            onLaunchFailed(instance, result.message || 'Engine runtime environment is not installed.');
          } else if (onDeploy) {
            onDeploy(instance);
          }
        }
      }
    } finally {
      setIsActing(false);
    }
  };

  const handleStop = async () => {
    if (!onStop) return;
    setIsActing(true);
    try {
      await onStop(instance.id);
    } finally {
      setIsActing(false);
    }
  };

  return (
    <div
      onClick={handleCardClick}
      className="group relative flex flex-col justify-between p-5 rounded-2xl bg-slate-900/60 hover:bg-slate-800/60 border border-white/[0.08] hover:border-indigo-500/40 transition-all duration-200 cursor-pointer shadow-lg hover:shadow-indigo-500/5 hover:-translate-y-0.5"
    >
      <div>
        {/* Card Header: Icon, Status, and Context Menu */}
        <div className="flex items-center justify-between mb-4">
          <div className="w-12 h-12 rounded-xl bg-slate-800/80 border border-white/[0.08] flex items-center justify-center text-indigo-400 group-hover:scale-110 transition-transform">
            <Icon className="w-6 h-6" />
          </div>

          <div className="flex items-center space-x-2">
            {/* Status Pill Badge */}
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                isRunning
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : isReady
                  ? 'bg-indigo-500/10 text-indigo-300 border border-indigo-500/20'
                  : instance.status === 'not_installed'
                  ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  : 'bg-slate-800 text-slate-400 border border-slate-700'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                  isRunning
                    ? 'bg-emerald-400 animate-pulse'
                    : isReady
                    ? 'bg-indigo-400'
                    : instance.status === 'not_installed'
                    ? 'bg-amber-400'
                    : 'bg-slate-500'
                }`}
              />
              <span className="capitalize">{instance.status.replace('_', ' ')}</span>
            </span>

            {/* Context Menu Button (for non-builtins) */}
            {!instance.is_builtin && (
              <div className="relative" ref={menuRef} data-stop-propagation>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsMenuOpen(!isMenuOpen);
                  }}
                  title="Instance options"
                  className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
                >
                  <MoreVertical className="w-4 h-4" />
                </button>

                {/* Dropdown Menu Popup */}
                {isMenuOpen && (
                  <div className="absolute right-0 top-full mt-1.5 w-44 rounded-xl bg-slate-900 border border-slate-700 shadow-2xl p-1 z-50 text-xs">
                    {onConfigure && (
                      <button
                        onClick={() => {
                          setIsMenuOpen(false);
                          onConfigure(instance);
                        }}
                        className="flex items-center w-full px-2.5 py-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                      >
                        <Settings className="w-3.5 h-3.5 mr-2 text-slate-400" />
                        <span>Configure Engine</span>
                      </button>
                    )}

                    {onViewLogs && (
                      <button
                        onClick={() => {
                          setIsMenuOpen(false);
                          onViewLogs(instance);
                        }}
                        className="flex items-center w-full px-2.5 py-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                      >
                        <FileText className="w-3.5 h-3.5 mr-2 text-slate-400" />
                        <span>View Logs</span>
                      </button>
                    )}

                    {onOpenDirectory && instance.install_path && (
                      <button
                        onClick={() => {
                          setIsMenuOpen(false);
                          onOpenDirectory(instance);
                        }}
                        className="flex items-center w-full px-2.5 py-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                      >
                        <FolderOpen className="w-3.5 h-3.5 mr-2 text-slate-400" />
                        <span>Open Directory</span>
                      </button>
                    )}

                    {instance.endpoint && (
                      <button
                        onClick={() => {
                          setIsMenuOpen(false);
                          window.open(instance.endpoint!, '_blank');
                        }}
                        className="flex items-center w-full px-2.5 py-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                      >
                        <ExternalLink className="w-3.5 h-3.5 mr-2 text-slate-400" />
                        <span>Open Browser</span>
                      </button>
                    )}

                    <div className="my-1 border-t border-slate-800" />

                    {onUninstall && (
                      <button
                        onClick={() => {
                          setIsMenuOpen(false);
                          onUninstall(instance);
                        }}
                        className="flex items-center w-full px-2.5 py-1.5 rounded-lg text-red-400 hover:bg-red-500/10 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5 mr-2 text-red-400" />
                        <span>{instance.is_managed ? 'Uninstall' : 'Remove Connection'}</span>
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Name and Version */}
        <h3 className="text-base font-bold text-slate-100 group-hover:text-indigo-300 transition-colors">
          {instance.name}
        </h3>
        <div className="text-xs text-slate-500 font-mono mb-2">
          {instance.version || (instance.is_managed ? 'Managed' : 'External Path')}
        </div>

        {/* Capabilities Pills */}
        {instance.capabilities && instance.capabilities.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {instance.capabilities.map((cap) => (
              <span
                key={cap}
                className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-slate-800/80 text-slate-400 border border-slate-700/50"
              >
                {cap}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Card Footer Actions */}
      <div className="pt-5 mt-4 border-t border-white/[0.06] flex items-center justify-between" data-stop-propagation>
        {instance.is_builtin ? (
          <button
            onClick={() => {
              if (instance.type === 'canvas') setActiveView('canvas');
              else if (instance.type === 'agents') onOpenAgent?.();
            }}
            className="text-xs font-semibold text-indigo-400 group-hover:text-indigo-300 flex items-center space-x-1"
          >
            <span>Open {instance.name}</span>
            <span className="group-hover:translate-x-1 transition-transform">→</span>
          </button>
        ) : isRunning ? (
          <div className="flex items-center justify-between w-full">
            <button
              onClick={() => {
                const view = instance.type as ViewType;
                setActiveView(view);
              }}
              className="text-xs font-semibold text-emerald-400 hover:text-emerald-300 flex items-center space-x-1"
            >
              <span>Switch to View</span>
              <span>→</span>
            </button>
            <button
              onClick={handleStop}
              disabled={isActing}
              className="flex items-center space-x-1 px-2.5 py-1 text-xs font-medium text-slate-300 hover:text-red-300 bg-slate-800 hover:bg-red-500/20 rounded border border-slate-700 hover:border-red-500/30 transition-colors"
            >
              <Square className="w-3 h-3 text-red-400" />
              <span>Stop</span>
            </button>
          </div>
        ) : isNotInstalled ? (
          <div className="flex items-center justify-between w-full">
            <span className="text-xs text-amber-500/90 font-medium">
              {t('engine_not_installed_title', lang) || 'Not Installed'}
            </span>
            <button
              onClick={handleStart}
              disabled={isActing}
              className="flex items-center space-x-1 px-3 py-1 text-xs font-medium text-white bg-amber-600 hover:bg-amber-500 rounded transition-colors disabled:opacity-50 shadow-sm shadow-amber-600/30"
            >
              <Download className="w-3 h-3" />
              <span>{t('btn_install_engine', lang) || 'Deploy'}</span>
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-between w-full">
            <span className="text-xs text-slate-500">Offline</span>
            <button
              onClick={handleStart}
              disabled={isActing}
              className="flex items-center space-x-1 px-3 py-1 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded transition-colors disabled:opacity-50"
            >
              <Play className="w-3 h-3" />
              <span>{isActing ? 'Booting...' : 'Start'}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
