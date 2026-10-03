import React from 'react';
import { GpuStats } from '../../stores/useHardwareStore';
import { Thermometer, Zap, HardDrive, Cpu } from 'lucide-react';

interface GpuDetailPopoverProps {
  stats: GpuStats;
}

export const GpuDetailPopover: React.FC<GpuDetailPopoverProps> = ({ stats }) => {
  const totalGb = (stats.vram_total_mb / 1024).toFixed(1);
  const usedGb = (stats.vram_used_mb / 1024).toFixed(1);
  const pct = stats.vram_total_mb > 0
    ? Math.min(100, Math.round((stats.vram_used_mb / stats.vram_total_mb) * 100))
    : 0;

  const barColor = pct > 80 ? 'bg-rose-500' : pct > 50 ? 'bg-amber-400' : 'bg-emerald-400';

  return (
    <div
      role="tooltip"
      className="absolute top-full mt-2 right-0 w-80 bg-slate-900/95 backdrop-blur-md border border-slate-700/80 rounded-xl shadow-2xl p-4 text-xs text-slate-200 z-50 pointer-events-auto select-none"
    >
      {/* Header: GPU Model & Driver */}
      <div className="pb-2.5 mb-2.5 border-b border-slate-800">
        <div className="flex items-center gap-1.5 font-semibold text-slate-100 text-sm">
          <Cpu className="w-4 h-4 text-indigo-400 shrink-0" />
          <span className="truncate">{stats.name}</span>
        </div>
        {stats.driver_version && (
          <div className="text-[11px] text-slate-400 mt-0.5">
            Driver: <span className="font-mono text-slate-300">{stats.driver_version}</span>
          </div>
        )}
      </div>

      {/* Primary Metrics: Temp, Utilization, VRAM */}
      <div className="space-y-2 mb-3">
        {stats.temperature_c !== null && (
          <div className="flex items-center justify-between text-slate-300">
            <span className="flex items-center gap-1.5 text-slate-400">
              <Thermometer className="w-3.5 h-3.5 text-amber-400" />
              Temperature
            </span>
            <span className="font-mono font-medium">{stats.temperature_c}°C</span>
          </div>
        )}

        {stats.utilization_pct !== null && (
          <div className="flex items-center justify-between text-slate-300">
            <span className="flex items-center gap-1.5 text-slate-400">
              <Zap className="w-3.5 h-3.5 text-sky-400" />
              GPU Utilization
            </span>
            <span className="font-mono font-medium">{stats.utilization_pct}%</span>
          </div>
        )}

        <div>
          <div className="flex items-center justify-between text-slate-300 mb-1">
            <span className="flex items-center gap-1.5 text-slate-400">
              <HardDrive className="w-3.5 h-3.5 text-purple-400" />
              VRAM Memory
            </span>
            <span className="font-mono font-medium">
              {usedGb}G / {totalGb}G <span className="text-slate-400 text-[11px]">({pct}%)</span>
            </span>
          </div>
          <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${barColor}`}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      </div>

      {/* Per-process breakdown */}
      <div className="pt-2 border-t border-slate-800">
        <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-1.5">
          Active Compute Tasks
        </div>
        {stats.processes.length === 0 ? (
          <div className="text-[11px] text-slate-500 italic py-1">
            No dedicated compute processes running
          </div>
        ) : (
          <div className="space-y-1 bg-slate-950/60 rounded-lg p-2 border border-slate-800/60 max-h-32 overflow-y-auto">
            {stats.processes.map((proc) => {
              const procMb = proc.vram_used_mb;
              const procDisplay =
                procMb >= 1024 ? `${(procMb / 1024).toFixed(1)} GB` : `${procMb} MB`;
              return (
                <div
                  key={proc.pid}
                  className="flex items-center justify-between text-[11px] text-slate-300 py-0.5"
                >
                  <span className="truncate pr-2 font-medium text-slate-200">
                    {proc.process_name}
                  </span>
                  <span className="font-mono text-slate-400 shrink-0">{procDisplay}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
