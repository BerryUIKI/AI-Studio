import React, { useEffect } from 'react';
import { Package, Search, Filter, ShieldCheck, RefreshCw, AlertCircle } from 'lucide-react';
import { useModelHubStore, HubModel } from '../../stores/useModelHubStore';
import { useDownloadStore } from '../../stores/useDownloadStore';
import { HubModelCard } from './HubModelCard';

interface ModelHubViewProps {
  onInstallModel?: (model: HubModel) => void;
  onUseCloudModel?: (model: HubModel) => void;
}

export const ModelHubView: React.FC<ModelHubViewProps> = ({
  onInstallModel,
  onUseCloudModel,
}) => {
  const {
    models,
    evaluations,
    hardwareSummary,
    selectedCategory,
    selectedArchitecture,
    searchQuery,
    onlyCompatible,
    isLoading,
    error,
    setCategory,
    setSearchQuery,
    setOnlyCompatible,
    fetchCatalog,
  } = useModelHubStore();

  useEffect(() => {
    fetchCatalog();
  }, [fetchCatalog, selectedCategory, selectedArchitecture]);

  const categories = [
    { id: 'all', label: 'All Items' },
    { id: 'checkpoint', label: 'Checkpoints' },
    { id: 'lora', label: 'LoRAs' },
    { id: 'controlnet', label: 'ControlNet' },
    { id: 'upscaler', label: 'Upscalers' },
    { id: 'vae', label: 'VAEs' },
  ];

  // Client-side filtering for search query & compatible only
  const filteredModels = models.filter((model) => {
    // Keyword match
    const q = searchQuery.toLowerCase().trim();
    const matchesQuery =
      !q ||
      model.name.toLowerCase().includes(q) ||
      model.architecture.toLowerCase().includes(q) ||
      model.author.toLowerCase().includes(q) ||
      (model.tags && model.tags.some((t) => t.toLowerCase().includes(q)));

    if (!matchesQuery) return false;

    // Compatible only filter
    if (onlyCompatible) {
      const evaluation = evaluations[model.id];
      if (evaluation && evaluation.tier === 'unsupported') {
        return false;
      }
    }

    return true;
  });

  const startDownload = useDownloadStore((state) => state.startDownload);
  const setDrawerOpen = useDownloadStore((state) => state.setDrawerOpen);

  const handleInstall = (model: HubModel) => {
    if (onInstallModel) {
      onInstallModel(model);
    } else {
      startDownload(model.id);
      setDrawerOpen(true);
    }
  };

  const handleUseCloud = (model: HubModel) => {
    if (onUseCloudModel) {
      onUseCloudModel(model);
    } else {
      console.log('Switch to cloud mode for model:', model.id);
    }
  };

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

          {/* Quick Hardware & Diagnostics Summary Badge */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-300">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>
                {hardwareSummary
                  ? `${hardwareSummary.gpu_name} (${(hardwareSummary.vram_total_mb / 1024).toFixed(0)}G)`
                  : 'Hardware Diagnostics Active'}
              </span>
            </div>
            <button
              onClick={() => fetchCatalog()}
              title="Refresh catalog and re-evaluate hardware"
              className="p-2 rounded-xl bg-slate-900/60 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-white transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Search & Filter Controls */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          {/* Category Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
            {categories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setCategory(cat.id)}
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

        {/* Error banner if network/API failure */}
        {error && (
          <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Responsive Model Cards Grid */}
        {filteredModels.length === 0 ? (
          <div className="p-12 rounded-3xl bg-slate-900/30 border border-white/[0.06] flex flex-col items-center justify-center text-center">
            <Package className="w-12 h-12 text-slate-600 mb-3" />
            <h3 className="text-sm font-bold text-slate-300 mb-1">No Matching Models Found</h3>
            <p className="text-xs text-slate-500">
              Try adjusting your search query, selecting &quot;All Items&quot;, or unchecking &quot;Compatible Only&quot;.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {filteredModels.map((model) => (
              <HubModelCard
                key={model.id}
                model={model}
                evaluation={evaluations[model.id]}
                hardwareSummary={hardwareSummary}
                onInstall={handleInstall}
                onUseCloud={handleUseCloud}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
