import React, { useState, useRef } from 'react';
import { ModelEvaluation, HardwareSummary } from '../../stores/useModelHubStore';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { t } from '../../i18n/translations';
import { ShieldCheck, AlertCircle, Cpu, HardDrive, Zap, Info } from 'lucide-react';

interface CompatibilityBadgeProps {
  evaluation?: ModelEvaluation | null;
  hardwareSummary?: HardwareSummary | null;
  modelName: string;
}

export const CompatibilityBadge: React.FC<CompatibilityBadgeProps> = ({
  evaluation,
  hardwareSummary,
  modelName,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const enterTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const leaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleMouseEnter = () => {
    if (leaveTimerRef.current) clearTimeout(leaveTimerRef.current);
    enterTimerRef.current = setTimeout(() => setIsOpen(true), 150);
  };

  const handleMouseLeave = () => {
    if (enterTimerRef.current) clearTimeout(enterTimerRef.current);
    leaveTimerRef.current = setTimeout(() => setIsOpen(false), 120);
  };

  if (!evaluation) {
    return (
      <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-800 text-slate-400 border border-slate-700">
        <span className="w-1.5 h-1.5 rounded-full bg-slate-500" />
        <span>Evaluating...</span>
      </div>
    );
  }

  const getBadgeStyle = () => {
    switch (evaluation.tier) {
      case 'optimal':
        return {
          pill: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30 hover:border-emerald-500/60',
          dot: 'bg-emerald-400 shadow-sm shadow-emerald-400/50',
          icon: ShieldCheck,
        };
      case 'playable_offload':
        return {
          pill: 'bg-amber-500/10 text-amber-300 border-amber-500/30 hover:border-amber-500/60',
          dot: 'bg-amber-400 shadow-sm shadow-amber-400/50',
          icon: Info,
        };
      case 'heavy_paging':
        return {
          pill: 'bg-orange-500/10 text-orange-300 border-orange-500/30 hover:border-orange-500/60',
          dot: 'bg-orange-400 shadow-sm shadow-orange-400/50',
          icon: AlertCircle,
        };
      case 'unsupported':
      default:
        return {
          pill: 'bg-rose-500/10 text-rose-300 border-rose-500/30 hover:border-rose-500/60',
          dot: 'bg-rose-400 shadow-sm shadow-rose-400/50',
          icon: AlertCircle,
        };
    }
  };

  const style = getBadgeStyle();
  const Icon = style.icon;

  const { getEffectiveLanguage } = useSettingsStore();
  const lang = getEffectiveLanguage();

  const getDisplayTierLabel = (): string => {
    if (!evaluation) return '';
    if (evaluation.notes && evaluation.notes.toLowerCase().includes('cpu')) {
      const cpuLabel = t('tier_cpu_mode', lang);
      if (cpuLabel && cpuLabel !== 'tier_cpu_mode') return cpuLabel;
    }
    const tierKey = `tier_${evaluation.tier}`;
    const localized = t(tierKey, lang);
    if (localized && localized !== tierKey) {
      return localized;
    }
    return evaluation.tier_label;
  };

  return (
    <div
      className="relative inline-block"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium border transition-colors cursor-pointer select-none ${style.pill}`}
        title="View hardware compatibility & memory diagnostic breakdown"
      >
        <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
        <Icon className="w-3 h-3" />
        <span>{getDisplayTierLabel()}</span>
      </button>

      {/* Hover Diagnostic Breakdown Tooltip */}
      {isOpen && (
        <div
          role="tooltip"
          className="absolute bottom-full mb-2 left-0 w-80 bg-slate-900/95 backdrop-blur-md border border-slate-700/80 rounded-xl shadow-2xl p-4 text-xs text-slate-200 z-50 pointer-events-auto select-none animate-in fade-in zoom-in-95 duration-100"
        >
          {/* Header */}
          <div className="pb-2 mb-2.5 border-b border-slate-800">
            <div className="font-semibold text-slate-100 text-sm flex items-center justify-between">
              <span>Memory Runnability</span>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${style.pill}`}>
                {evaluation.tier}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 truncate mt-0.5">{modelName}</p>
          </div>

          {/* Model Requirements */}
          <div className="space-y-1.5 mb-3 text-slate-300">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-slate-400">
                <HardDrive className="w-3.5 h-3.5 text-purple-400" />
                Required Footprint
              </span>
              <span className="font-mono font-medium">
                {(evaluation.required_vram_mb / 1024).toFixed(1)} GB
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-slate-400">
                <Zap className="w-3.5 h-3.5 text-sky-400" />
                Est. Gen Speed
              </span>
              <span className="font-mono font-medium text-indigo-300">
                {evaluation.estimated_latency_sec}
              </span>
            </div>
          </div>

          {/* User System Specs */}
          {hardwareSummary && (
            <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80 mb-3 space-y-1 text-[11px]">
              <div className="flex items-center gap-1.5 text-slate-400 font-medium mb-1">
                <Cpu className="w-3.5 h-3.5 text-indigo-400" />
                <span>Your Hardware:</span>
              </div>
              <div className="flex justify-between text-slate-300">
                <span className="truncate pr-2">{hardwareSummary.gpu_name}</span>
                <span className="font-mono shrink-0">
                  {(hardwareSummary.vram_total_mb / 1024).toFixed(0)} GB VRAM
                </span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>System RAM:</span>
                <span className="font-mono">
                  {(hardwareSummary.ram_avail_mb / 1024).toFixed(1)}G free / {(hardwareSummary.ram_total_mb / 1024).toFixed(0)}G
                </span>
              </div>
            </div>
          )}

          {/* Diagnostic Notes */}
          <div className="text-[11px] text-slate-300 bg-slate-800/50 rounded-lg p-2 border border-slate-700/50 leading-relaxed">
            {evaluation.notes}
          </div>
        </div>
      )}
    </div>
  );
};
