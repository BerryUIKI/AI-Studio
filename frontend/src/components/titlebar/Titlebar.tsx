import React, { useEffect, useState } from 'react';
import {
  Sparkles,
  Upload,
  Cloud,
  Server,
  Layers,
  Play,
  Trash2,
  Cpu,
  ExternalLink,
  Power,
  Minus,
  Square,
  Copy,
  X,
} from 'lucide-react';
import { isTauri } from '@tauri-apps/api/core';
import { getCurrentWindow } from '@tauri-apps/api/window';

export interface ComfyStatus {
  online: boolean;
  port: number;
  devices?: { name: string }[];
}

export interface RuntimeStatus {
  installed: boolean;
  running: boolean;
  pid?: number;
}

export interface TitlebarProps {
  backendOnline: boolean;
  comfyStatus: ComfyStatus | null;
  runtimeStatus: RuntimeStatus | null;
  toggleRuntime: () => void;
  onImportImage: () => void;
  onOpenCloud: () => void;
  onOpenManager: () => void;
  showAgentPanel: boolean;
  onToggleAgent: () => void;
  showNodePalette: boolean;
  onToggleNodePalette: () => void;
  onRunWorkflow: () => void;
  isExecuting: boolean;
  hasNodes: boolean;
  onClearCanvas: () => void;
  onMaximizeChange?: (isMaximized: boolean) => void;
}

export const Titlebar: React.FC<TitlebarProps> = ({
  backendOnline,
  comfyStatus,
  runtimeStatus,
  toggleRuntime,
  onImportImage,
  onOpenCloud,
  onOpenManager,
  showAgentPanel,
  onToggleAgent,
  showNodePalette,
  onToggleNodePalette,
  onRunWorkflow,
  isExecuting,
  hasNodes,
  onClearCanvas,
  onMaximizeChange,
}) => {
  const [isDesktop, setIsDesktop] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);

  useEffect(() => {
    let unlistenResize: (() => void) | undefined;

    const setupTauri = async () => {
      try {
        if (!isTauri()) return;
        setIsDesktop(true);
        const appWindow = getCurrentWindow();
        const initialMax = await appWindow.isMaximized();
        setIsMaximized(initialMax);
        onMaximizeChange?.(initialMax);

        unlistenResize = await appWindow.onResized(async () => {
          const max = await appWindow.isMaximized();
          setIsMaximized(max);
          onMaximizeChange?.(max);
        });
      } catch (err) {
        console.warn('Tauri window API not available or errored:', err);
      }
    };

    setupTauri();

    return () => {
      if (unlistenResize) {
        unlistenResize();
      }
    };
  }, [onMaximizeChange]);

  const handleMinimize = async () => {
    try {
      if (isTauri()) {
        const appWindow = getCurrentWindow();
        await appWindow.minimize();
      }
    } catch (e) {
      console.error('Failed to minimize window:', e);
    }
  };

  const handleToggleMaximize = async () => {
    try {
      if (isTauri()) {
        const appWindow = getCurrentWindow();
        await appWindow.toggleMaximize();
        const max = await appWindow.isMaximized();
        setIsMaximized(max);
        onMaximizeChange?.(max);
      }
    } catch (e) {
      console.error('Failed to toggle maximize:', e);
    }
  };

  const handleClose = async () => {
    try {
      if (isTauri()) {
        const appWindow = getCurrentWindow();
        await appWindow.close();
      }
    } catch (e) {
      console.error('Failed to close window:', e);
    }
  };

  const handleTitlebarDoubleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    // Only toggle maximize if clicking directly on the drag surface, not on interactive child controls
    const target = e.target as HTMLElement;
    if (target.closest('button') || target.closest('a') || target.closest('input')) {
      return;
    }
    handleToggleMaximize();
  };

  return (
    <header
      data-tauri-drag-region
      onDoubleClick={handleTitlebarDoubleClick}
      className="h-11 border-b border-white/[0.08] bg-slate-900/90 backdrop-blur-md px-3 flex items-center justify-between z-30 select-none transition-all duration-200"
    >
      {/* Left: Brand Identity */}
      <div className="flex items-center gap-2.5 min-w-max pointer-events-none" data-tauri-drag-region>
        <div className="flex items-center justify-center w-6 h-6 rounded-lg bg-gradient-to-tr from-indigo-600 via-indigo-500 to-purple-500 shadow-md shadow-indigo-500/20 text-white">
          <Sparkles className="w-3.5 h-3.5" />
        </div>
        <div className="flex items-center gap-2">
          <span className="font-semibold text-xs tracking-wide text-slate-100">
            Berry AI Studio
          </span>
          <span className="text-[10px] font-mono font-medium px-1.5 py-0.2 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
            v0.1.0
          </span>
        </div>
      </div>

      {/* Center: Action Controls */}
      <div className="flex items-center gap-1.5" data-no-drag>
        {/* Import Image Button */}
        <button
          onClick={onImportImage}
          title="Import an image directly onto the canvas"
          className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-slate-800/80 hover:bg-slate-700/90 text-slate-200 text-xs font-medium border border-slate-700/60 hover:border-slate-600 transition shadow-sm"
        >
          <Upload className="w-3 h-3 text-indigo-400" />
          <span>Import</span>
        </button>

        {/* Cloud BYOK Settings Button */}
        <button
          onClick={onOpenCloud}
          title="Configure BYOK Cloud Providers (OpenAI, Fal.ai, SiliconFlow)"
          className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-slate-800/80 hover:bg-slate-700/90 text-slate-200 text-xs font-medium border border-slate-700/60 hover:border-slate-600 transition shadow-sm"
        >
          <Cloud className="w-3 h-3 text-sky-400" />
          <span>Cloud BYOK</span>
        </button>

        {/* Environment Manager Button */}
        <button
          onClick={onOpenManager}
          title="Open Environment Manager (Engines, Models, Updates, Core)"
          className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-slate-800/80 hover:bg-slate-700/90 text-slate-200 text-xs font-medium border border-slate-700/60 hover:border-slate-600 transition shadow-sm"
        >
          <Server className="w-3 h-3 text-purple-400" />
          <span>Environment</span>
        </button>

        {/* Conversational Agent Assistant Button */}
        <button
          onClick={onToggleAgent}
          title="Conversational AI Assistant (Natural Language Workflows & Human-in-the-Loop)"
          className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium border transition shadow-sm ${
            showAgentPanel
              ? 'bg-indigo-600/30 text-indigo-300 border-indigo-500/50 shadow-indigo-500/10'
              : 'bg-slate-800/80 hover:bg-slate-700/90 text-slate-200 border-slate-700/60'
          }`}
        >
          <Sparkles className="w-3 h-3 text-amber-400" />
          <span>Agent</span>
        </button>

        {/* Toggle Node Palette for Power Users */}
        <button
          onClick={onToggleNodePalette}
          title="Toggle Node Palette (Node Graph Mode)"
          className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium border transition shadow-sm ${
            showNodePalette
              ? 'bg-indigo-600/20 text-indigo-300 border-indigo-500/40'
              : 'bg-slate-800/80 hover:bg-slate-700/90 text-slate-400 border-slate-700/60'
          }`}
        >
          <Layers className="w-3 h-3" />
          <span>Nodes</span>
        </button>

        {/* Graph Execution Runner */}
        {showNodePalette && (
          <button
            onClick={onRunWorkflow}
            disabled={!hasNodes || isExecuting}
            className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-medium shadow-md shadow-indigo-600/20 transition"
          >
            <Play className={`w-3 h-3 fill-current ${isExecuting ? 'animate-pulse' : ''}`} />
            <span>{isExecuting ? 'Running...' : 'Run Graph'}</span>
          </button>
        )}

        {/* Clear Canvas */}
        <button
          onClick={onClearCanvas}
          disabled={!hasNodes || isExecuting}
          title="Clear canvas objects"
          className="p-1 rounded-md bg-slate-800/80 hover:bg-slate-700/90 disabled:opacity-40 disabled:cursor-not-allowed text-slate-400 hover:text-rose-400 border border-slate-700/60 transition shadow-sm"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      </div>

      {/* Right: Status Indicators + Window Controls */}
      <div className="flex items-center gap-2">
        {/* Backend & ComfyUI Status Indicators */}
        <div className="flex items-center gap-1.5 text-xs" data-no-drag>
          {/* Backend Connection */}
          <div
            className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-slate-800/70 border border-white/[0.06] text-[11px]"
            title={`Backend Service: ${backendOnline ? 'Online (Ready)' : 'Connecting or Offline'}`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                backendOnline ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50' : 'bg-rose-400 animate-pulse'
              }`}
            />
            <span className="text-slate-300 font-medium">Backend</span>
          </div>

          {/* ComfyUI Indicator */}
          <div
            className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-slate-800/70 border border-white/[0.06] text-[11px]"
            title={`ComfyUI Engine: ${comfyStatus?.online ? 'Online' : 'Standby'}`}
          >
            <Cpu className={`w-3 h-3 ${comfyStatus?.online ? 'text-emerald-400' : 'text-slate-400'}`} />
            <span className="text-slate-300">
              {comfyStatus?.online ? 'Engine Active' : 'Standby'}
            </span>
            {comfyStatus?.online && (
              <a
                href="http://127.0.0.1:8188"
                target="_blank"
                rel="noreferrer"
                title="Open ComfyUI native web interface in a new tab"
                className="p-0.5 rounded text-slate-400 hover:text-indigo-400 transition"
              >
                <ExternalLink className="w-2.5 h-2.5" />
              </a>
            )}
            {runtimeStatus?.installed && (
              <button
                onClick={toggleRuntime}
                title={runtimeStatus.running ? 'Stop isolated engine' : 'Start isolated engine'}
                className="p-0.5 rounded hover:bg-slate-700 text-slate-400 hover:text-indigo-400 transition"
              >
                <Power className={`w-2.5 h-2.5 ${runtimeStatus.running ? 'text-emerald-400' : 'text-slate-400'}`} />
              </button>
            )}
          </div>
        </div>

        {/* Windows / Desktop Native Window Control Buttons */}
        {isDesktop ? (
          <div className="flex items-center ml-1 border-l border-white/[0.06] pl-1 h-8" data-no-drag>
            {/* Minimize */}
            <button
              onClick={handleMinimize}
              title="Minimize"
              className="w-8 h-8 rounded flex items-center justify-center text-slate-400 hover:text-slate-100 hover:bg-white/[0.08] active:bg-white/[0.12] transition-colors"
            >
              <Minus className="w-3.5 h-3.5" />
            </button>

            {/* Maximize / Restore */}
            <button
              onClick={handleToggleMaximize}
              title={isMaximized ? 'Restore Down' : 'Maximize'}
              className="w-8 h-8 rounded flex items-center justify-center text-slate-400 hover:text-slate-100 hover:bg-white/[0.08] active:bg-white/[0.12] transition-colors"
            >
              {isMaximized ? (
                <Copy className="w-3 h-3 rotate-180" />
              ) : (
                <Square className="w-3 h-3" />
              )}
            </button>

            {/* Close */}
            <button
              onClick={handleClose}
              title="Close"
              className="w-8 h-8 rounded flex items-center justify-center text-slate-400 hover:text-white hover:bg-rose-600 active:bg-rose-700 transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <div className="px-2 py-0.5 rounded bg-slate-800/40 text-[10px] text-slate-500 font-mono">
            Web Mode
          </div>
        )}
      </div>
    </header>
  );
};
