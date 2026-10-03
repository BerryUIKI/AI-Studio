import React from 'react';
import { ArrowDownToLine, ChevronUp, Loader2 } from 'lucide-react';
import { useDownloadStore } from '../../stores/useDownloadStore';

export const FloatingDownloadWidget: React.FC = () => {
  const tasks = useDownloadStore((state) => state.tasks);
  const isDrawerOpen = useDownloadStore((state) => state.isDrawerOpen);
  const toggleDrawer = useDownloadStore((state) => state.toggleDrawer);
  const getActiveCount = useDownloadStore((state) => state.getActiveCount);
  const getTotalSpeedBps = useDownloadStore((state) => state.getTotalSpeedBps);

  const activeCount = getActiveCount();
  const totalSpeed = getTotalSpeedBps();

  // If there are no tasks at all or drawer is already open, do not render floating pill
  if (tasks.length === 0 || isDrawerOpen) {
    return null;
  }

  const formatSpeed = (bps: number) => {
    if (bps >= 1024 * 1024 * 1024) return `${(bps / (1024 * 1024 * 1024)).toFixed(1)} GB/s`;
    if (bps >= 1024 * 1024) return `${(bps / (1024 * 1024)).toFixed(1)} MB/s`;
    if (bps >= 1024) return `${(bps / 1024).toFixed(1)} KB/s`;
    return `${bps} B/s`;
  };

  const hasDownloading = tasks.some((t) => t.status === 'downloading');

  return (
    <button
      onClick={toggleDrawer}
      className="fixed bottom-6 right-6 z-40 flex items-center gap-3 px-4 py-2.5 bg-neutral-900/90 hover:bg-neutral-800/95 text-neutral-100 rounded-full border border-neutral-700/80 shadow-2xl backdrop-blur-md transition-all duration-200 hover:scale-105 active:scale-95 group"
    >
      <div className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-500/20 text-blue-400">
        {hasDownloading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <ArrowDownToLine className="w-3.5 h-3.5" />
        )}
      </div>

      <div className="flex items-center gap-2 text-xs font-medium">
        {activeCount > 0 ? (
          <>
            <span className="text-neutral-200 font-semibold">{activeCount} Downloading</span>
            <span className="text-neutral-500">·</span>
            <span className="text-emerald-400 font-mono">{formatSpeed(totalSpeed)}</span>
          </>
        ) : (
          <span className="text-neutral-300">{tasks.length} Downloads</span>
        )}
      </div>

      <ChevronUp className="w-4 h-4 text-neutral-400 group-hover:text-neutral-200 transition-transform group-hover:-translate-y-0.5" />
    </button>
  );
};
