import React, { useState } from 'react';
import {
  Palette,
  Puzzle,
  Image as ImageIcon,
  Bot,
  Plus,
  Search,
  Sparkles,
} from 'lucide-react';
import { useNavigationStore } from '../../stores/useNavigationStore';

export interface LauncherHubProps {
  comfyOnline?: boolean;
  comfyRunning?: boolean;
  webuiOnline?: boolean;
  webuiRunning?: boolean;
  onStartComfy?: () => void;
  onStartWebui?: () => void;
  onOpenAddEngine?: () => void;
}

export const LauncherHub: React.FC<LauncherHubProps> = ({
  comfyOnline = false,
  comfyRunning = false,
  webuiOnline = false,
  webuiRunning = false,
  onStartComfy,
  onStartWebui,
  onOpenAddEngine,
}) => {
  const { setActiveView } = useNavigationStore();
  const [searchQuery, setSearchQuery] = useState('');

  const instances = [
    {
      id: 'canvas',
      name: 'Infinite Canvas',
      category: 'Workspace',
      version: 'Built-in · v0.1.0',
      icon: Palette,
      status: 'ready',
      statusLabel: 'Ready',
      description: 'Unified visual node workspace with contextual generative tools.',
      actionLabel: 'Open Canvas',
      onAction: () => setActiveView('canvas'),
    },
    {
      id: 'comfyui',
      name: 'ComfyUI Engine',
      category: 'Engine',
      version: 'Local · v0.3.8',
      icon: Puzzle,
      status: comfyRunning || comfyOnline ? 'running' : 'stopped',
      statusLabel: comfyRunning || comfyOnline ? 'Running' : 'Stopped',
      description: 'Node-based modular diffusion pipeline for advanced generation.',
      actionLabel: comfyRunning || comfyOnline ? 'Open ComfyUI' : 'Start Engine',
      onAction: () => {
        if (comfyRunning || comfyOnline) {
          setActiveView('comfyui');
        } else if (onStartComfy) {
          onStartComfy();
        }
      },
    },
    {
      id: 'webui',
      name: 'SD WebUI',
      category: 'Engine',
      version: 'Local · Automatic1111',
      icon: ImageIcon,
      status: webuiRunning || webuiOnline ? 'running' : 'stopped',
      statusLabel: webuiRunning || webuiOnline ? 'Running' : 'Stopped',
      description: 'Classic Stable Diffusion WebUI with checkpoint & lora management.',
      actionLabel: webuiRunning || webuiOnline ? 'Open WebUI' : 'Start WebUI',
      onAction: () => {
        if (webuiRunning || webuiOnline) {
          setActiveView('webui');
        } else if (onStartWebui) {
          onStartWebui();
        }
      },
    },
    {
      id: 'agents',
      name: 'AI Agents Studio',
      category: 'Workspace',
      version: 'Built-in · Multi-Agent',
      icon: Bot,
      status: 'ready',
      statusLabel: 'Ready',
      description: 'Autonomous multi-modal agents for automated workflow generation.',
      actionLabel: 'Open Agents',
      onAction: () => setActiveView('agents'),
    },
  ];

  const filteredInstances = instances.filter((inst) =>
    inst.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    inst.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

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
            className="w-full pl-10 pr-4 py-2.5 bg-slate-900/80 border border-white/[0.1] rounded-xl text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 transition-all shadow-inner"
          />
        </div>
      </div>

      {/* Grid of Workspaces and Instances */}
      <div className="max-w-5xl mx-auto w-full">
        <div className="flex items-center justify-between mb-4 px-1">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Available Environments ({filteredInstances.length})
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {/* Workspaces & Engines Cards */}
          {filteredInstances.map((inst) => {
            const Icon = inst.icon;
            const isRunning = inst.status === 'running';

            return (
              <div
                key={inst.id}
                onClick={inst.onAction}
                className="group relative flex flex-col justify-between p-5 rounded-2xl bg-slate-900/60 hover:bg-slate-800/60 border border-white/[0.08] hover:border-indigo-500/40 transition-all duration-200 cursor-pointer shadow-lg hover:shadow-indigo-500/5 hover:-translate-y-0.5"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-12 h-12 rounded-xl bg-slate-800/80 border border-white/[0.08] flex items-center justify-center text-indigo-400 group-hover:scale-110 transition-transform">
                      <Icon className="w-6 h-6" />
                    </div>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        isRunning
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : inst.status === 'ready'
                          ? 'bg-indigo-500/10 text-indigo-300 border border-indigo-500/20'
                          : 'bg-slate-800 text-slate-400 border border-slate-700'
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                          isRunning ? 'bg-emerald-400 animate-pulse' : inst.status === 'ready' ? 'bg-indigo-400' : 'bg-slate-500'
                        }`}
                      />
                      {inst.statusLabel}
                    </span>
                  </div>

                  <h3 className="text-base font-bold text-slate-100 group-hover:text-indigo-300 transition-colors">
                    {inst.name}
                  </h3>
                  <div className="text-xs text-slate-500 font-mono mb-2">{inst.version}</div>
                  <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">
                    {inst.description}
                  </p>
                </div>

                <div className="pt-5 mt-4 border-t border-white/[0.06] flex items-center justify-between">
                  <span className="text-xs font-semibold text-indigo-400 group-hover:text-indigo-300 flex items-center space-x-1">
                    <span>{inst.actionLabel}</span>
                    <span className="group-hover:translate-x-1 transition-transform">→</span>
                  </span>
                </div>
              </div>
            );
          })}

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
