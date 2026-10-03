import React from 'react';
import {
  X,
  Pause,
  Play,
  Trash2,
  CheckCircle2,
  AlertCircle,
  HardDrive,
  Download,
} from 'lucide-react';
import { useDownloadStore, DownloadTask } from '../../stores/useDownloadStore';

export const DownloadManagerDrawer: React.FC = () => {
  const isDrawerOpen = useDownloadStore((state) => state.isDrawerOpen);
  const setDrawerOpen = useDownloadStore((state) => state.setDrawerOpen);
  const tasks = useDownloadStore((state) => state.tasks);
  const pauseTask = useDownloadStore((state) => state.pauseTask);
  const resumeTask = useDownloadStore((state) => state.resumeTask);
  const cancelTask = useDownloadStore((state) => state.cancelTask);

  if (!isDrawerOpen) return null;

  const activeCount = tasks.filter((t) => t.status === 'downloading' || t.status === 'pending').length;
  const completedCount = tasks.filter((t) => t.status === 'completed').length;

  const formatBytes = (bytes: number) => {
    if (bytes >= 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
    if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${bytes} B`;
  };

  const formatSpeed = (bps: number) => {
    if (bps >= 1024 * 1024 * 1024) return `${(bps / (1024 * 1024 * 1024)).toFixed(1)} GB/s`;
    if (bps >= 1024 * 1024) return `${(bps / (1024 * 1024)).toFixed(1)} MB/s`;
    if (bps >= 1024) return `${(bps / 1024).toFixed(1)} KB/s`;
    return `${bps} B/s`;
  };

  const formatEta = (sec?: number | null) => {
    if (sec === undefined || sec === null) return '';
    if (sec < 60) return `${sec}s left`;
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}m ${s}s left`;
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={() => setDrawerOpen(false)}
      />

      {/* Drawer Body */}
      <div className="relative w-full max-w-lg bg-neutral-900 border-l border-neutral-800 shadow-2xl flex flex-col h-full z-10 animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-800 bg-neutral-900/80">
          <div className="flex items-center gap-2">
            <Download className="w-5 h-5 text-blue-400" />
            <h2 className="text-base font-semibold text-neutral-100">Downloads</h2>
            <span className="text-xs text-neutral-400 bg-neutral-800 px-2 py-0.5 rounded-full border border-neutral-700">
              {activeCount} Active · {completedCount} Completed
            </span>
          </div>
          <button
            onClick={() => setDrawerOpen(false)}
            className="p-1.5 text-neutral-400 hover:text-neutral-100 hover:bg-neutral-800 rounded-md transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Task List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {tasks.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-neutral-500 gap-2">
              <Download className="w-8 h-8 opacity-40" />
              <p className="text-sm">No download tasks yet</p>
            </div>
          ) : (
            tasks.map((task: DownloadTask) => {
              const isFinished = task.status === 'completed';
              const isPaused = task.status === 'paused';
              const isDownloading = task.status === 'downloading';
              const isFailed = task.status === 'failed';

              return (
                <div
                  key={task.task_id}
                  className="bg-neutral-800/60 border border-neutral-700/60 rounded-xl p-4 space-y-3 hover:border-neutral-600/60 transition-colors"
                >
                  {/* Task Header */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        {isFinished && <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />}
                        {isFailed && <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />}
                        <h3 className="text-sm font-semibold text-neutral-200 truncate">
                          {task.model_name}
                        </h3>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-neutral-400 mt-1">
                        <HardDrive className="w-3 h-3 text-neutral-500" />
                        <span className="truncate">
                          Target: {task.target_engine.toUpperCase()} ({task.target_path})
                        </span>
                      </div>
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-1.5 shrink-0">
                      {isDownloading && (
                        <button
                          onClick={() => pauseTask(task.task_id)}
                          title="Pause"
                          className="p-1.5 text-neutral-400 hover:text-amber-400 hover:bg-neutral-700 rounded-lg transition-colors"
                        >
                          <Pause className="w-4 h-4" />
                        </button>
                      )}
                      {isPaused && (
                        <button
                          onClick={() => resumeTask(task.task_id)}
                          title="Resume"
                          className="p-1.5 text-neutral-400 hover:text-emerald-400 hover:bg-neutral-700 rounded-lg transition-colors"
                        >
                          <Play className="w-4 h-4" />
                        </button>
                      )}
                      {!isFinished && (
                        <button
                          onClick={() => cancelTask(task.task_id)}
                          title="Cancel"
                          className="p-1.5 text-neutral-400 hover:text-rose-400 hover:bg-neutral-700 rounded-lg transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Progress Bar */}
                  <div className="space-y-1.5">
                    <div className="w-full bg-neutral-900 rounded-full h-1.5 overflow-hidden">
                      <div
                        className={`h-full transition-all duration-300 ${
                          isFinished
                            ? 'bg-emerald-500'
                            : isFailed
                            ? 'bg-rose-500'
                            : isPaused
                            ? 'bg-amber-500'
                            : 'bg-blue-500'
                        }`}
                        style={{ width: `${task.progress_pct}%` }}
                      />
                    </div>

                    {/* Progress Info Footer */}
                    <div className="flex items-center justify-between text-xs font-mono text-neutral-400">
                      <span>
                        {task.progress_pct}% · {formatBytes(task.downloaded_bytes)} / {formatBytes(task.total_bytes)}
                      </span>
                      <div className="flex items-center gap-2">
                        {isDownloading && (
                          <>
                            <span className="text-emerald-400 font-medium">{formatSpeed(task.speed_bps)}</span>
                            {task.eta_seconds !== null && task.eta_seconds !== undefined && (
                              <span className="text-neutral-500">({formatEta(task.eta_seconds)})</span>
                            )}
                          </>
                        )}
                        {isPaused && <span className="text-amber-400 font-medium">Paused</span>}
                        {isFinished && <span className="text-emerald-400 font-medium">Installed</span>}
                        {isFailed && <span className="text-rose-400 font-medium">Failed</span>}
                      </div>
                    </div>
                  </div>

                  {/* Failure details if any */}
                  {isFailed && task.error_message && (
                    <p className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-md p-2">
                      {task.error_message}
                    </p>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
