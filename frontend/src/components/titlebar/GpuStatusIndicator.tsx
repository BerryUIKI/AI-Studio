import React, { useEffect, useRef } from 'react';
import { useHardwareStore } from '../../stores/useHardwareStore';
import { GpuDetailPopover } from './GpuDetailPopover';
import { Cloud, Cpu } from 'lucide-react';

export const GpuStatusIndicator: React.FC = () => {
  const { stats, isPopoverOpen, setIsPopoverOpen, fetchGpuStats } = useHardwareStore();
  const enterTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const leaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Poll GPU statistics: 3s standard, 1s when detail popover is open
  useEffect(() => {
    fetchGpuStats();
    const intervalMs = isPopoverOpen ? 1000 : 3000;
    const interval = setInterval(() => {
      fetchGpuStats();
    }, intervalMs);

    return () => clearInterval(interval);
  }, [fetchGpuStats, isPopoverOpen]);

  const handleMouseEnter = () => {
    if (leaveTimerRef.current) {
      clearTimeout(leaveTimerRef.current);
      leaveTimerRef.current = null;
    }
    enterTimerRef.current = setTimeout(() => {
      setIsPopoverOpen(true);
    }, 200);
  };

  const handleMouseLeave = () => {
    if (enterTimerRef.current) {
      clearTimeout(enterTimerRef.current);
      enterTimerRef.current = null;
    }
    leaveTimerRef.current = setTimeout(() => {
      setIsPopoverOpen(false);
    }, 150);
  };

  // If no dedicated GPU detected or telemetry offline, show Cloud Mode
  if (!stats || !stats.has_gpu) {
    return (
      <div
        className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-slate-800/40 border border-white/[0.04] text-[11px] text-slate-400 select-none"
        title="Running in Cloud-First Mode (No dedicated NVIDIA GPU detected)"
        data-no-drag
      >
        <Cloud className="w-3 h-3 text-slate-500" />
        <span className="text-slate-400 font-medium">Cloud Mode</span>
      </div>
    );
  }

  // Format short model name (e.g., "RTX 4090", "GTX 1660 Ti", etc.)
  const shortName = stats.name
    .replace(/NVIDIA\s+/i, '')
    .replace(/GeForce\s+/i, '')
    .trim();

  const totalGb = Math.round(stats.vram_total_mb / 1024);
  const usedGb = (stats.vram_used_mb / 1024).toFixed(1);
  const pct = stats.vram_total_mb > 0
    ? Math.min(100, Math.round((stats.vram_used_mb / stats.vram_total_mb) * 100))
    : 0;

  const dotColor = pct > 80 ? 'bg-rose-500 shadow-rose-500/50' : pct > 50 ? 'bg-amber-400 shadow-amber-400/50' : 'bg-emerald-400 shadow-emerald-400/50';

  return (
    <div
      className="relative"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      data-no-drag
    >
      <button
        onClick={() => setIsPopoverOpen(!isPopoverOpen)}
        className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-slate-800/70 hover:bg-slate-700/80 border border-white/[0.08] hover:border-slate-600 transition-colors text-[11px] text-slate-200 select-none shadow-sm cursor-pointer"
        title="View live GPU temperature, utilization, and process VRAM distribution"
      >
        <span className={`w-1.5 h-1.5 rounded-full shadow-sm ${dotColor}`} />
        <Cpu className="w-3 h-3 text-indigo-400" />
        <span className="font-semibold text-slate-100">{shortName}</span>
        <span className="text-slate-400 font-mono">
          {usedGb}G / {totalGb}G ({pct}%)
        </span>
      </button>

      {isPopoverOpen && <GpuDetailPopover stats={stats} />}
    </div>
  );
};
