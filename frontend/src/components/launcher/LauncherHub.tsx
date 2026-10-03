import React, { useEffect } from 'react';
import {
  Plus,
  Search,
  Sparkles,
  RefreshCw,
} from 'lucide-react';
import { useEngineStore, EngineInstance } from '../../stores/useEngineStore';
import { InstanceCard } from './InstanceCard';

export interface LauncherHubProps {
  onOpenAddEngine?: () => void;
  onConfigureEngine?: (instance: EngineInstance) => void;
  onViewLogs?: (instance: EngineInstance) => void;
  onOpenDirectory?: (instance: EngineInstance) => void;
  onUninstallEngine?: (instance: EngineInstance) => void;
  onOpenAgent?: () => void;
  onDeployEngine?: (instance: EngineInstance) => void;
  onLaunchFailed?: (instance: EngineInstance, error: string) => void;
  // Legacy props kept for backward-compatibility
  comfyOnline?: boolean;
  comfyRunning?: boolean;
  webuiOnline?: boolean;
  webuiRunning?: boolean;
  onStartComfy?: () => void;
  onStartWebui?: () => void;
}

export const LauncherHub: React.FC<LauncherHubProps> = ({
  onOpenAddEngine,
  onConfigureEngine,
  onViewLogs,
  onOpenDirectory,
  onUninstallEngine,
  onOpenAgent,
  onDeployEngine,
  onLaunchFailed,
}) => {
  const {
    instances,
    isLoading,
    searchQuery,
    setSearchQuery,
    fetchInstances,
    startEngine,
    stopEngine,
  } = useEngineStore();

  useEffect(() => {
    fetchInstances();
    const interval = setInterval(fetchInstances, 6000);
    return () => clearInterval(interval);
  }, [fetchInstances]);

  const filteredInstances = instances.filter((inst) => {
    const q = searchQuery.toLowerCase();
    return (
      inst.name.toLowerCase().includes(q) ||
      inst.type.toLowerCase().includes(q) ||
      (inst.capabilities && inst.capabilities.some((c) => c.toLowerCase().includes(q)))
    );
  });

  return (
    <div className="flex flex-col w-full h-full overflow-y-auto bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100 p-8 select-none">
      {/* Brand Hero Header */}
      <div className="flex flex-col items-center justify-center pt-8 pb-10 text-center max-w-2xl mx-auto">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-medium mb-4">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Berry AI Studio Launcher Hub</span>
        </div>
        <h1 className="text-4xl font-extrabold tracking-tight text-white mb-3">
          Creative Hub & Workspaces
        </h1>
        <p className="text-slate-400 text-sm max-w-md">
          Launch your creative workspace, orchestrate local diffusion engines, or automate with multi-modal AI agents.
        </p>

        {/* Global Search Bar */}
        <div className="relative w-full mt-6">
          <Search className="absolute left-3.5 top-3 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search workspaces and engine instances..."
            className="w-full pl-10 pr-10 py-2.5 bg-slate-900/80 border border-white/[0.1] rounded-xl text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 transition-all shadow-inner"
          />
          {isLoading && (
            <RefreshCw className="absolute right-3.5 top-3 w-4 h-4 text-slate-500 animate-spin" />
          )}
        </div>
      </div>

      {/* Grid of Workspaces and Instances */}
      <div className="max-w-5xl mx-auto w-full">
        <div className="flex items-center justify-between mb-4 px-1">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Available Environments ({filteredInstances.length})
          </span>
          <button
            onClick={() => fetchInstances()}
            title="Refresh instances status"
            className="text-xs text-slate-400 hover:text-slate-200 flex items-center space-x-1"
          >
            <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {/* Workspaces & Engines Cards */}
          {filteredInstances.map((instance) => (
            <InstanceCard
              key={instance.id}
              instance={instance}
              onStart={startEngine}
              onStop={stopEngine}
              onConfigure={onConfigureEngine}
              onViewLogs={onViewLogs}
              onOpenDirectory={onOpenDirectory}
              onUninstall={onUninstallEngine}
              onOpenAgent={onOpenAgent}
              onDeploy={onDeployEngine}
              onLaunchFailed={onLaunchFailed}
            />
          ))}

          {/* Add New Instance Card */}
          <div
            onClick={onOpenAddEngine}
            className="group relative flex flex-col items-center justify-center p-6 rounded-2xl bg-slate-900/30 hover:bg-slate-800/40 border-2 border-dashed border-white/[0.1] hover:border-indigo-500/40 transition-all duration-200 cursor-pointer min-h-[200px]"
          >
            <div className="w-12 h-12 rounded-xl bg-slate-800/60 border border-white/[0.08] flex items-center justify-center text-slate-400 group-hover:text-indigo-400 group-hover:scale-110 transition-all mb-3">
              <Plus className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-bold text-slate-200 group-hover:text-indigo-300 transition-colors">
              Add Engine Instance
            </h3>
            <p className="text-xs text-slate-500 text-center mt-1">
              Connect external directory or deploy a fresh environment
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
