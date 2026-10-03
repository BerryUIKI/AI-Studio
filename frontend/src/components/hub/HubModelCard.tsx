import React from 'react';
import { HubModel, ModelEvaluation, HardwareSummary } from '../../stores/useModelHubStore';
import { CompatibilityBadge } from './CompatibilityBadge';
import { Download, Cloud, Check, HardDrive } from 'lucide-react';

interface HubModelCardProps {
  model: HubModel;
  evaluation?: ModelEvaluation | null;
  hardwareSummary?: HardwareSummary | null;
  onInstall: (model: HubModel) => void;
  onUseCloud?: (model: HubModel) => void;
}

export const HubModelCard: React.FC<HubModelCardProps> = ({
  model,
  evaluation,
  hardwareSummary,
  onInstall,
  onUseCloud,
}) => {
  const sizeGb = (model.size_bytes / (1024 * 1024 * 1024)).toFixed(1);
  const isUnsupported = evaluation?.tier === 'unsupported';

  return (
    <div className="group relative flex flex-col justify-between rounded-2xl bg-slate-900/60 hover:bg-slate-800/60 border border-white/[0.08] hover:border-indigo-500/40 transition-all duration-200 overflow-hidden shadow-lg hover:shadow-indigo-500/5 hover:-translate-y-0.5">
      {/* Top Media Preview Area */}
      <div className="relative w-full h-44 bg-slate-950 overflow-hidden">
        <img
          src={model.preview_image_url}
          alt={model.name}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          onError={(e) => {
            // Fallback gradient if preview image fails to load
            (e.target as HTMLElement).style.display = 'none';
          }}
        />

        {/* Gradient Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent" />

        {/* Top Badges */}
        <div className="absolute top-3 left-3 right-3 flex items-center justify-between">
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold uppercase tracking-wider bg-black/60 backdrop-blur-md text-indigo-300 border border-white/10">
            {model.architecture}
          </span>
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono bg-black/60 backdrop-blur-md text-slate-300 border border-white/10">
            <HardDrive className="w-3 h-3 text-slate-400" />
            <span>{sizeGb} GB</span>
          </span>
        </div>

        {/* Quantization tag */}
        {model.quantization && (
          <div className="absolute bottom-3 left-3">
            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-600/80 text-white shadow">
              {model.quantization}
            </span>
          </div>
        )}
      </div>

      {/* Card Content Area */}
      <div className="p-4 flex-1 flex flex-col justify-between">
        <div>
          {/* Title & Author */}
          <div className="mb-1.5">
            <h3 className="text-sm font-bold text-slate-100 group-hover:text-indigo-300 transition-colors truncate">
              {model.name}
            </h3>
            <p className="text-[11px] text-slate-500">by {model.author}</p>
          </div>

          {/* Description */}
          <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed mb-3">
            {model.description}
          </p>

          {/* Tags */}
          {model.tags && model.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-3">
              {model.tags.slice(0, 3).map((tag) => (
                <span
                  key={tag}
                  className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-800/80 text-slate-400 border border-slate-700/50"
                >
                  #{tag}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Bottom Section: Compatibility Badge & Action Button */}
        <div className="pt-3 border-t border-slate-800/80 space-y-3">
          <div className="flex items-center justify-between">
            <CompatibilityBadge
              evaluation={evaluation}
              hardwareSummary={hardwareSummary}
              modelName={model.name}
            />
            <span className="text-[11px] font-mono text-slate-500">
              {model.recommended_resolution[0]}x{model.recommended_resolution[1]}
            </span>
          </div>

          {/* Primary Action Button */}
          {model.is_installed ? (
            <button
              disabled
              className="flex items-center justify-center gap-1.5 w-full py-2 rounded-xl text-xs font-semibold bg-slate-800/80 text-emerald-400 border border-emerald-500/20 cursor-default"
            >
              <Check className="w-3.5 h-3.5" />
              <span>Installed to Engine</span>
            </button>
          ) : isUnsupported ? (
            <button
              onClick={() => onUseCloud?.(model)}
              className="flex items-center justify-center gap-1.5 w-full py-2 rounded-xl text-xs font-semibold bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-md shadow-indigo-600/20 transition-all cursor-pointer"
              title="This model exceeds local hardware VRAM limits; generate seamlessly using Cloud BYOK mode."
            >
              <Cloud className="w-3.5 h-3.5 text-purple-200" />
              <span>Use Cloud Mode</span>
            </button>
          ) : (
            <button
              onClick={() => onInstall(model)}
              className="flex items-center justify-center gap-1.5 w-full py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20 transition-all cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Install to Engine</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
