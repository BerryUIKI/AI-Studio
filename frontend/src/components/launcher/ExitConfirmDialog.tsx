import React, { useState } from 'react';
import { AlertTriangle, X, CheckSquare, Square } from 'lucide-react';

export interface RunningEngineItem {
  id: string;
  name: string;
}

interface ExitConfirmDialogProps {
  isOpen: boolean;
  runningEngines: RunningEngineItem[];
  activeTasksCount?: number;
  onKeepRunning: (remember: boolean) => void;
  onCloseAllAndExit: (remember: boolean, force?: boolean) => void;
  onCancel: () => void;
}

export const ExitConfirmDialog: React.FC<ExitConfirmDialogProps> = ({
  isOpen,
  runningEngines,
  activeTasksCount = 0,
  onKeepRunning,
  onCloseAllAndExit,
  onCancel,
}) => {
  const [rememberChoice, setRememberChoice] = useState(false);

  if (!isOpen) return null;

  const hasTasks = activeTasksCount > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm select-none">
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden p-6 text-slate-100 animate-in fade-in zoom-in-95 duration-150">
        {/* Close Button */}
        <button
          onClick={onCancel}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          title="Cancel"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Warning Icon & Header */}
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 shrink-0">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">
              {hasTasks ? 'Active Generation Tasks Running' : 'Engines Still Running'}
            </h2>
            <p className="text-xs text-slate-400">
              {hasTasks
                ? `${activeTasksCount} creative task(s) in progress`
                : 'Background inference services are active'}
            </p>
          </div>
        </div>

        {/* Running Tasks or Engines List */}
        <div className="mb-4">
          {hasTasks ? (
            <p className="text-xs text-amber-300/90 mb-2 font-medium">
              Closing now will abort running tasks unless you Keep Running.
            </p>
          ) : (
            <p className="text-xs text-slate-300 mb-2">
              The following managed engines are currently running in the background:
            </p>
          )}
          {runningEngines.length > 0 && (
            <div className="space-y-1.5 bg-slate-950/60 rounded-xl p-3 border border-slate-800">
              {runningEngines.map((engine) => (
                <div key={engine.id} className="flex items-center gap-2 text-xs text-slate-200">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400/50" />
                  <span className="font-semibold">{engine.name}</span>
                  <span className="text-[11px] text-slate-500">(Active process)</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Remember Choice Checkbox */}
        <div
          onClick={() => setRememberChoice(!rememberChoice)}
          className="flex items-center gap-2 mb-6 cursor-pointer text-xs text-slate-300 hover:text-white transition-colors"
        >
          {rememberChoice ? (
            <CheckSquare className="w-4 h-4 text-indigo-400" />
          ) : (
            <Square className="w-4 h-4 text-slate-500" />
          )}
          <span>Remember my choice in Settings</span>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-2.5">
          <button
            onClick={onCancel}
            className="px-3.5 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => onKeepRunning(rememberChoice)}
            className="px-3.5 py-2 rounded-xl text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition-colors"
          >
            Keep Running
          </button>
          <button
            onClick={() => onCloseAllAndExit(rememberChoice)}
            className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-rose-600 hover:bg-rose-500 shadow-lg shadow-rose-600/20 transition-colors"
          >
            Close All & Exit
          </button>
        </div>
      </div>
    </div>
  );
};
