import React, { useState } from 'react';
import { Package, Search, Filter, ShieldCheck, DownloadCloud, Sparkles } from 'lucide-react';

export const ModelHubView: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [onlyCompatible, setOnlyCompatible] = useState(false);

  const categories = [
    { id: 'all', label: 'All Items' },
    { id: 'checkpoint', label: 'Checkpoints' },
    { id: 'lora', label: 'LoRAs' },
    { id: 'controlnet', label: 'ControlNet' },
    { id: 'upscaler', label: 'Upscalers' },
    { id: 'vae', label: 'VAEs' },
  ];

  return (
    <div className="flex flex-col w-full h-full overflow-y-auto bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100 p-8 select-none">
      <div className="max-w-7xl mx-auto w-full space-y-6">
        {/* Header Hero Section */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-6 border-b border-white/[0.08] gap-4">
          <div className="flex items-center space-x-3.5">
            <div className="w-12 h-12 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shadow-inner">
              <Package className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight text-white">Model Hub</h1>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                  Hardware Aware
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Discover, evaluate hardware runnability, and install curated open-weight models.
              </p>
            </div>
          </div>

          {/* Quick Hardware & Mirror Status Badge */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-300">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>4-Tier Memory Diagnostics Active</span>
            </div>
          </div>
        </div>

        {/* Search & Filter Controls */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          {/* Category Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
            {categories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                  selectedCategory === cat.id
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                    : 'bg-slate-900/60 hover:bg-slate-800/80 text-slate-400 hover:text-slate-200 border border-slate-800'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* Search Bar & Compatibility Checkbox */}
          <div className="flex items-center gap-3 w-full sm:w-auto">
            <div className="relative flex-1 sm:w-72">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search models, base architectures..."
                className="w-full pl-9 pr-3 py-1.5 bg-slate-900/80 border border-slate-800 hover:border-slate-700 focus:border-indigo-500 rounded-xl text-xs text-slate-100 placeholder-slate-500 focus:outline-none transition-colors"
              />
            </div>

            <button
              onClick={() => setOnlyCompatible(!onlyCompatible)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border transition-colors ${
                onlyCompatible
                  ? 'bg-emerald-600/15 text-emerald-300 border-emerald-500/30'
                  : 'bg-slate-900/60 hover:bg-slate-800 text-slate-400 border-slate-800'
              }`}
              title="Filter to show only models that run within your GPU VRAM or system RAM"
            >
              <Filter className="w-3.5 h-3.5" />
              <span>Compatible Only</span>
            </button>
          </div>
        </div>

        {/* Placeholder Content Area (Shell for MH-M2/M3 Model Cards) */}
        <div className="p-12 rounded-3xl bg-slate-900/30 border border-white/[0.06] flex flex-col items-center justify-center text-center">
          <div className="w-16 h-16 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4 shadow-lg shadow-indigo-600/5">
            <DownloadCloud className="w-8 h-8" />
          </div>
          <h3 className="text-base font-bold text-white mb-1.5">
            Curated Model Catalog & Hardware Evaluator
          </h3>
          <p className="text-xs text-slate-400 max-w-md mb-6 leading-relaxed">
            The Model Hub shell is ready. Connecting backend catalog registry, real-time 4-tier
            VRAM/RAM memory diagnostics, and resumable download acceleration in upcoming milestones.
          </p>
          <div className="flex items-center gap-2 text-[11px] text-slate-500 font-mono">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>Milestone MH-M1 Initialized · Ready for Catalog Integration</span>
          </div>
        </div>
      </div>
    </div>
  );
};
