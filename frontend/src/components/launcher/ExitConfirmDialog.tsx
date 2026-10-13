import { useUiText } from '../../i18n/useUiText';
import { Dialog } from '../ui/Dialog';
import React, { useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';

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
  const ui = useUiText();
  const [rememberChoice, setRememberChoice] = useState(false);

  if (!isOpen) return null;

  const hasTasks = activeTasksCount > 0;

  return (
    <Dialog title={ui("ui_exit_berry")} onClose={onCancel} className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm select-none">
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden p-6 text-slate-100 animate-in fade-in zoom-in-95 duration-150">
        {/* Close Button */}
        <button
          onClick={onCancel}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          title={ui("ui_cancel")} aria-label={ui("ui_cancel_exit")}
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
              {hasTasks ? ui("ui_active_generation_tasks_running") : ui("ui_engines_still_running")}
            </h2>
            <p className="text-xs text-slate-400">
              {hasTasks
                ? ui("ui_value_creative_task_s_in_progress", { value1: activeTasksCount })
                : ui("ui_background_inference_services_are_active")}
            </p>
          </div>
        </div>

        {/* Running Tasks or Engines List */}
        <div className="mb-4">
          {hasTasks ? (
            <p className="text-xs text-amber-300/90 mb-2 font-medium">
              {ui("ui_closing_now_will_abort_running_tasks_unless_you")}</p>
          ) : (
            <p className="text-xs text-slate-300 mb-2">
              {ui("ui_the_following_managed_engines_are_currently_running_in")}</p>
          )}
          {runningEngines.length > 0 && (
            <div className="space-y-1.5 bg-slate-950/60 rounded-xl p-3 border border-slate-800">
              {runningEngines.map((engine) => (
                <div key={engine.id} className="flex items-center gap-2 text-xs text-slate-200">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400/50" />
                  <span className="font-semibold">{engine.name}</span>
                  <span className="text-[11px] text-slate-500">{ui("ui_active_process")}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Remember Choice Checkbox */}
        <label className="flex items-center gap-2 mb-6 text-xs text-slate-300">
          <input type="checkbox" checked={rememberChoice} onChange={(event) => setRememberChoice(event.target.checked)} />
          <span>{ui("ui_remember_my_choice_in_settings")}</span>
        </label>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-2.5">
          <button
            onClick={onCancel}
            className="px-3.5 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            {ui("ui_cancel")}</button>
          <button
            onClick={() => onKeepRunning(rememberChoice)}
            className="px-3.5 py-2 rounded-xl text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition-colors"
          >
            {ui("ui_keep_running")}</button>
          <button
            onClick={() => onCloseAllAndExit(rememberChoice)}
            className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-rose-600 hover:bg-rose-500 shadow-lg shadow-rose-600/20 transition-colors"
          >
            {ui("ui_close_all_exit")}</button>
        </div>
      </div>
    </Dialog>
  );
};
