import { useUiText } from '../../i18n/useUiText';
import React, { useRef, useState } from 'react';
import { ExternalLink, RefreshCw, FolderOpen, Play, Power, Download } from 'lucide-react';

interface EmbeddedEngineViewProps {
  title: string;
  endpoint: string | null;
  isRunning: boolean;
  isStarting?: boolean;
  isManaged?: boolean;
  error?: string | null;
  isInstalled?: boolean;
  onStartEngine: () => Promise<void> | void;
  onDeployEngine?: () => void;
  onOpenDirectory?: () => void;
}

export const EmbeddedEngineView: React.FC<EmbeddedEngineViewProps> = ({
  title,
  endpoint,
  isRunning,
  isStarting: processStarting = false,
  isManaged = true,
  error,
  isInstalled = true,
  onStartEngine,
  onDeployEngine,
  onOpenDirectory,
}) => {
  const ui = useUiText();
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [submittingStart, setSubmittingStart] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const isStarting = submittingStart || processStarting;

  const engineUrl = (() => {
    try {
      const url = new URL(endpoint || '');
      return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;
    } catch { return null; }
  })();

  const handleRefresh = () => {
    if (iframeRef.current && engineUrl) {
      setIsRefreshing(true);
      iframeRef.current.src = engineUrl;
      setTimeout(() => setIsRefreshing(false), 800);
    }
  };

  const handleOpenBrowser = () => {
    if (engineUrl) window.open(engineUrl, '_blank', 'noopener,noreferrer');
  };

  const handleStart = async () => {
    if (isStarting || !isManaged) return;
    setSubmittingStart(true);
    setStartError(null);
    try {
      await onStartEngine();
    } catch (cause: unknown) {
      setStartError(cause instanceof Error ? cause.message : 'The engine could not be started.');
    } finally {
      setSubmittingStart(false);
    }
  };

  return (
    <div className="flex flex-col w-full h-full bg-slate-950 text-slate-100 overflow-hidden">
      {/* Utility Toolbar */}
      <header className="flex items-center justify-between px-4 py-2 bg-slate-900 border-b border-white/[0.08] select-none z-20">
        <div className="flex items-center space-x-3">
          <span className="font-semibold text-sm text-slate-200">{title}</span>
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium ${
              isRunning ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-slate-800 text-slate-400 border border-slate-700'
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                isRunning ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'
              }`}
            />
            {isRunning ? engineUrl : isStarting ? ui('ui_starting') : ui("ui_stopped")}
          </span>
        </div>

        {/* Toolbar action buttons */}
        <div className="flex items-center space-x-2">
          {isRunning && engineUrl ? (
            <>
              <button
                onClick={handleRefresh}
                title={ui("ui_reload_interface")}
                className="flex items-center space-x-1 px-2.5 py-1 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition-colors"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
                <span>{ui("ui_reload")}</span>
              </button>
              <button
                onClick={handleOpenBrowser}
                title={ui("ui_open_in_system_browser")}
                className="flex items-center space-x-1 px-2.5 py-1 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition-colors"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>{ui("ui_browser")}</span>
              </button>
            </>
          ) : !isManaged ? null : !isInstalled ? (
            <button
              onClick={onDeployEngine}
              className="flex items-center space-x-1 px-3 py-1 text-xs font-medium text-white bg-amber-600 hover:bg-amber-500 rounded transition-colors shadow-sm shadow-amber-600/30"
            >
              <Download className="w-3.5 h-3.5" />
              <span>{ui("ui_deploy_2")}{title}</span>
            </button>
          ) : (
            <button
              onClick={handleStart}
              disabled={isStarting}
              className="flex items-center space-x-1 px-3 py-1 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded transition-colors disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5" />
              <span>{isStarting ? ui("ui_starting") : ui("ui_start_value", { value1: title })}</span>
            </button>
          )}

          {onOpenDirectory && (
            <button
              onClick={onOpenDirectory}
              title={ui("ui_open_install_folder")}
              className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded transition-colors"
            >
              <FolderOpen className="w-4 h-4" />
            </button>
          )}
        </div>
      </header>
      {(startError || error) && <p role="alert" className="border-b border-amber-800 bg-amber-950/40 p-4 text-sm text-amber-200">{startError || error}</p>}
      {isRunning && !engineUrl && <p role="alert" className="p-4 text-sm text-amber-200">The configured engine endpoint is unavailable or invalid. Check the connection settings.</p>}

      {/* Main View Area */}
      <main className="flex-1 relative w-full h-full bg-slate-950">
        {isRunning && engineUrl ? (
          <iframe
            ref={iframeRef}
            src={engineUrl}
            title={ui("ui_value_embedded_view", { value1: title })}
            className="w-full h-full border-0 bg-slate-900"
            sandbox="allow-same-origin allow-scripts allow-forms allow-downloads allow-modals allow-popups"
          />
        ) : !isManaged ? (
          <p role="status" className="p-8 text-sm text-slate-300">Start this external engine outside Berry, then refresh its connection. Berry does not control external processes.</p>
        ) : !isInstalled ? (
          <div className="flex flex-col items-center justify-center w-full h-full p-8 text-center select-none">
            <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mb-4 shadow-xl">
              <Download className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-bold text-slate-200 mb-2">{title} {ui("ui_is_not_installed_2")}</h2>
            <p className="text-sm text-slate-400 max-w-md mb-6 leading-relaxed">
              {ui("ui_berry_ai_studio_maintains_100_zero_host_pollution")}{title}.
            </p>
            <div className="flex items-center space-x-3">
              <button
                onClick={onDeployEngine}
                className="inline-flex items-center space-x-2 px-5 py-2.5 bg-amber-600 hover:bg-amber-500 text-white font-medium text-sm rounded-lg shadow-lg shadow-amber-600/25 transition-all"
              >
                <Download className="w-4 h-4" />
                <span>{ui("ui_deploy_2")}{title} {ui("ui_now")}</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center w-full h-full p-8 text-center select-none">
            <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-white/[0.08] flex items-center justify-center text-slate-400 mb-4 shadow-xl">
              <Power className="w-8 h-8 text-slate-500" />
            </div>
            <h2 className="text-xl font-bold text-slate-200 mb-2">{title} {ui("ui_is_not_running")}</h2>
            <p className="text-sm text-slate-400 max-w-md mb-6">
              {ui("ui_start_the_engine_process_to_access_its_native")}</p>
            <button
              onClick={handleStart}
              disabled={isStarting}
              className="inline-flex items-center space-x-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm rounded-lg shadow-lg shadow-indigo-600/20 transition-all disabled:opacity-50"
            >
              <Play className="w-4 h-4" />
              <span>{isStarting ? ui("ui_booting_engine") : ui("ui_start_value_now", { value1: title })}</span>
            </button>
          </div>
        )}
      </main>
    </div>
  );
};
