import React, { useRef, useState } from 'react';
import { ExternalLink, RefreshCw, FolderOpen, Play, Power } from 'lucide-react';

interface EmbeddedEngineViewProps {
  engineType: 'comfyui' | 'webui';
  title: string;
  port: number;
  isRunning: boolean;
  onStartEngine: () => Promise<void> | void;
  onOpenDirectory?: () => void;
}

export const EmbeddedEngineView: React.FC<EmbeddedEngineViewProps> = ({
  engineType: _engineType,
  title,
  port,
  isRunning,
  onStartEngine,
  onOpenDirectory,
}) => {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isStarting, setIsStarting] = useState(false);

  const engineUrl = `http://127.0.0.1:${port}`;

  const handleRefresh = () => {
    if (iframeRef.current) {
      setIsRefreshing(true);
      iframeRef.current.src = engineUrl;
      setTimeout(() => setIsRefreshing(false), 800);
    }
  };

  const handleOpenBrowser = () => {
    window.open(engineUrl, '_blank');
  };

  const handleStart = async () => {
    setIsStarting(true);
    try {
      await onStartEngine();
    } finally {
      setIsStarting(false);
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
            {isRunning ? `127.0.0.1:${port}` : 'Stopped'}
          </span>
        </div>

        {/* Toolbar action buttons */}
        <div className="flex items-center space-x-2">
          {isRunning ? (
            <>
              <button
                onClick={handleRefresh}
                title="Reload interface"
                className="flex items-center space-x-1 px-2.5 py-1 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition-colors"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
                <span>Reload</span>
              </button>
              <button
                onClick={handleOpenBrowser}
                title="Open in system browser"
                className="flex items-center space-x-1 px-2.5 py-1 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition-colors"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>Browser</span>
              </button>
            </>
          ) : (
            <button
              onClick={handleStart}
              disabled={isStarting}
              className="flex items-center space-x-1 px-3 py-1 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded transition-colors disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5" />
              <span>{isStarting ? 'Starting...' : `Start ${title}`}</span>
            </button>
          )}

          {onOpenDirectory && (
            <button
              onClick={onOpenDirectory}
              title="Open install folder"
              className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded transition-colors"
            >
              <FolderOpen className="w-4 h-4" />
            </button>
          )}
        </div>
      </header>

      {/* Main View Area */}
      <main className="flex-1 relative w-full h-full bg-slate-950">
        {isRunning ? (
          <iframe
            ref={iframeRef}
            src={engineUrl}
            title={`${title} Embedded View`}
            className="w-full h-full border-0 bg-slate-900"
            sandbox="allow-same-origin allow-scripts allow-forms allow-downloads allow-modals allow-popups"
          />
        ) : (
          <div className="flex flex-col items-center justify-center w-full h-full p-8 text-center select-none">
            <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-white/[0.08] flex items-center justify-center text-slate-400 mb-4 shadow-xl">
              <Power className="w-8 h-8 text-slate-500" />
            </div>
            <h2 className="text-xl font-bold text-slate-200 mb-2">{title} is not running</h2>
            <p className="text-sm text-slate-400 max-w-md mb-6">
              Start the engine process to access its native UI directly inside Berry AI Studio, or launch it from the Launcher Hub.
            </p>
            <button
              onClick={handleStart}
              disabled={isStarting}
              className="inline-flex items-center space-x-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm rounded-lg shadow-lg shadow-indigo-600/20 transition-all disabled:opacity-50"
            >
              <Play className="w-4 h-4" />
              <span>{isStarting ? 'Booting engine...' : `Start ${title} Now`}</span>
            </button>
          </div>
        )}
      </main>
    </div>
  );
};
