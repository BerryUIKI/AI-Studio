import React, { useState, useEffect, useRef } from 'react';
import { X, Terminal, CheckCircle2, AlertCircle } from 'lucide-react';
import { useEngineStore } from '../../stores/useEngineStore';

interface DeploymentDrawerProps {
  isOpen: boolean;
  engineType: 'comfyui' | 'webui';
  mirrorPreset?: string;
  onClose: () => void;
}

export const DeploymentDrawer: React.FC<DeploymentDrawerProps> = ({
  isOpen,
  engineType,
  mirrorPreset,
  onClose,
}) => {
  const [phase, setPhase] = useState<string>('checking');
  const [progressPercent, setProgressPercent] = useState<number>(10);
  const [logs, setLogs] = useState<string[]>([]);
  const [isCompleted, setIsCompleted] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const logEndRef = useRef<HTMLDivElement | null>(null);

  const { fetchInstances } = useEngineStore();

  useEffect(() => {
    if (!isOpen) return;

    // Reset state
    setPhase('checking');
    setProgressPercent(10);
    setLogs([`[INFO] Starting deployment of sandboxed ${engineType}...`]);
    setIsCompleted(false);
    setError(null);

    // Trigger installation
    fetch(`/api/v1/runtime/${engineType}/install`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: mirrorPreset ? JSON.stringify({ mirror_preset: mirrorPreset }) : undefined,
    }).then((response) => { if (!response.ok) throw new Error(`Installation request failed (${response.status})`); })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'Could not start installation'));

    // Poll installation manifest
    const pollInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/v1/runtime/${engineType}/manifest`);
        if (res.ok) {
          const manifest = await res.json();
          setPhase(manifest.phase);

          if (manifest.last_log_line) {
            setLogs((prev) => {
              if (prev[prev.length - 1] !== manifest.last_log_line) {
                return [...prev, manifest.last_log_line];
              }
              return prev;
            });
          }

          // Calculate percentage based on phase
          switch (manifest.phase) {
            case 'checking':
              setProgressPercent(15);
              break;
            case 'creating_venv':
              setProgressPercent(35);
              break;
            case 'downloading':
              setProgressPercent(60);
              break;
            case 'installing_deps':
              setProgressPercent(85);
              break;
            case 'completed':
              setProgressPercent(100);
              setIsCompleted(true);
              clearInterval(pollInterval);
              fetchInstances();
              break;
            case 'failed':
            case 'interrupted':
              setError(manifest.error_message || 'Installation encountered an error.');
              clearInterval(pollInterval);
              break;
          }
        }
      } catch {
        // Continue polling
      }
    }, 1500);

    return () => clearInterval(pollInterval);
  }, [isOpen, engineType, mirrorPreset, fetchInstances]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col bg-slate-900 border-l border-slate-800 shadow-2xl text-slate-100 select-none animate-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800 bg-slate-950/60">
        <div className="flex items-center space-x-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
            <Terminal className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-100">
              Deploying {engineType === 'comfyui' ? 'ComfyUI' : 'SD WebUI'}
            </h2>
            <p className="text-[11px] text-slate-400">Sandboxed isolated runtime</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Progress & Current Step */}
      <div className="px-5 py-4 bg-slate-950/40 border-b border-slate-800/80">
        <div className="flex items-center justify-between text-xs mb-2">
          <span className="font-semibold text-slate-300 capitalize">
            Phase: {phase.replace('_', ' ')}
          </span>
          <span className="font-mono text-indigo-400 font-bold">{progressPercent}%</span>
        </div>

        {/* Progress Bar */}
        <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${
              error ? 'bg-red-500' : isCompleted ? 'bg-emerald-500' : 'bg-indigo-600'
            }`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        {error && (
          <div className="mt-3 p-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400 flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {isCompleted && (
          <div className="mt-3 p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-400 flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
            <span>Engine successfully deployed and ready to run!</span>
          </div>
        )}
      </div>

      {/* Terminal Output */}
      <div className="flex-1 p-4 bg-slate-950 overflow-y-auto font-mono text-xs leading-relaxed text-slate-400 space-y-1">
        {logs.map((log, idx) => (
          <div key={idx} className="break-all whitespace-pre-wrap">
            <span className="text-slate-600 mr-2">&gt;</span>
            <span className={log.includes('ERROR') ? 'text-red-400' : log.includes('INFO') ? 'text-indigo-300' : 'text-slate-300'}>
              {log}
            </span>
          </div>
        ))}
        <div ref={logEndRef} />
      </div>

      {/* Footer Controls */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between">
        <span className="text-[11px] text-slate-500 font-mono">Zero Host Pollution Guaranteed</span>
        <button
          onClick={onClose}
          className="px-4 py-1.5 text-xs font-semibold text-white bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors border border-slate-700"
        >
          {isCompleted || error ? 'Close' : 'Minimize to Background'}
        </button>
      </div>
    </div>
  );
};
