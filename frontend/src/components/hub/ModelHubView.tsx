import { formatNumber } from '../../i18n/format';
import { useUiText } from '../../i18n/useUiText';
import React, { useEffect } from 'react';
import { Package, Search, Filter, ShieldCheck, RefreshCw, AlertCircle } from 'lucide-react';
import { useModelHubStore, HubModel } from '../../stores/useModelHubStore';
import { useDownloadStore } from '../../stores/useDownloadStore';
import { HubModelCard } from './HubModelCard';
import { useCreativeStore } from '../../stores/useCreativeStore';
import { useCreationSetupStore, localModelAvailable, localModelFilename, modelsForProvider, providerConnection } from '../../stores/useCreationSetupStore';
import { useEngineStore } from '../../stores/useEngineStore';
import { useNavigationStore } from '../../stores/useNavigationStore';

interface ModelHubViewProps {
  onInstallModel?: (model: HubModel) => void;
  onUseCloudModel?: (model: HubModel) => void;
}

export const ModelHubView: React.FC<ModelHubViewProps> = ({
  onInstallModel,
  onUseCloudModel,
}) => {
  const ui = useUiText();
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
    { id: 'all', label: ui("ui_all_items") },
    { id: 'checkpoint', label: 'Checkpoints' },
    { id: 'lora', label: 'LoRAs' },
    { id: 'controlnet', label: 'ControlNet' },
    { id: 'upscaler', label: 'Upscalers' },
    { id: 'vae', label: 'VAEs' },
    { id: 'llm', label: ui("ui_language_models") },
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

  const handleUseCloud = async (model: HubModel) => {
    if (onUseCloudModel) {
      onUseCloudModel(model);
    } else {
      await useCreationSetupStore.getState().refresh();
      const providers = useCreationSetupStore.getState().providers;
      const family = model.architecture.toLowerCase().includes('flux') ? 'flux'
        : model.architecture.toLowerCase().includes('sdxl') ? 'sdxl' : '';
      const provider = providers.find((item) => item.is_configured && modelsForProvider(item, 'txt2img').some((name) => family && name.toLowerCase().includes(family)));
      const targetModel = provider && modelsForProvider(provider, 'txt2img').find((name) => name.toLowerCase().includes(family));
      if (!provider || !targetModel) {
        useModelHubStore.setState({ error: 'No configured image provider offers this model family. Configure a supported provider in Settings → Cloud, then refresh.' });
        return;
      }
      useCreativeStore.getState().setConnectionId(providerConnection(provider.id));
      useCreativeStore.getState().setModel(targetModel);
      useCreativeStore.getState().setReferenceImage(null);
      useNavigationStore.getState().setActiveView('canvas');
    }
  };

  const handleUseModel = async (model: HubModel) => {
    await useCreationSetupStore.getState().refresh();
    await useEngineStore.getState().fetchInstances();
    const record = useCreationSetupStore.getState().models.find((item) => item.id === model.installed_model_id);
    const engine = record && useEngineStore.getState().instances.find((item) => item.status === 'running' && localModelAvailable(record, item.type));
    if (!record || !engine) {
      useModelHubStore.setState({ error: model.guidance || 'Start a compatible engine and validate this model in Models before use. Component models and language models need their own supported workflow.' });
      return;
    }
    useCreativeStore.getState().setConnectionId(engine.connection_id || engine.id);
    useCreativeStore.getState().setModel(localModelFilename(record));
    useCreativeStore.getState().setReferenceImage(null);
    useNavigationStore.getState().setActiveView('canvas');
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
                <h1 className="text-2xl font-bold tracking-tight text-white">{ui("ui_model_hub")}</h1>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                  {ui("ui_hardware_aware")}</span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                {ui("ui_discover_evaluate_hardware_runnability_and_install_curated_open")}</p>
            </div>
          </div>

          {/* Quick Hardware & Diagnostics Summary Badge */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-300">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>
                {hardwareSummary
                  ? ui("ui_value_valueg", { value1: hardwareSummary.gpu_name, value2: formatNumber((hardwareSummary.vram_total_mb / 1024), 0, 0) })
                  : ui("ui_hardware_diagnostics_active")}
              </span>
            </div>
            <button
              onClick={() => fetchCatalog()}
              title={ui("ui_refresh_catalog_and_re_evaluate_hardware")}
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
                placeholder={ui("ui_search_models_base_architectures")}
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
              title={ui("ui_filter_to_show_only_models_that_run_within")}
            >
              <Filter className="w-3.5 h-3.5" />
              <span>{ui("ui_compatible_only")}</span>
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
            <h3 className="text-sm font-bold text-slate-300 mb-1">{ui("ui_no_matching_models_found")}</h3>
            <p className="text-xs text-slate-500">
              {ui("ui_try_adjusting_your_search_query_selecting_all_items")}</p>
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
                onUseModel={handleUseModel}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
