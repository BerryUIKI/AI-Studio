import React from 'react';
import {
  Home,
  Palette,
  Package,
  Puzzle,
  Image as ImageIcon,
  Settings,
  ChevronLeft,
  Menu,
} from 'lucide-react';
import { useNavigationStore, ViewType } from '../../stores/useNavigationStore';

interface NavItem {
  id: ViewType;
  label: string;
  icon: React.ElementType;
  isEngine?: boolean;
}

const mainNavItems: NavItem[] = [
  { id: 'launcher', label: 'Launcher Hub', icon: Home },
  { id: 'canvas', label: 'Infinite Canvas', icon: Palette },
  { id: 'models', label: 'Model Hub', icon: Package },
  { id: 'comfyui', label: 'ComfyUI', icon: Puzzle, isEngine: true },
  { id: 'webui', label: 'SD WebUI', icon: ImageIcon, isEngine: true },
];

const bottomNavItems: NavItem[] = [
  { id: 'settings', label: 'Settings', icon: Settings },
];

export interface GlobalNavRailProps {
  comfyOnline?: boolean;
  comfyRunning?: boolean;
  webuiOnline?: boolean;
  webuiRunning?: boolean;
  isGenerating?: boolean;
}

export const GlobalNavRail: React.FC<GlobalNavRailProps> = ({
  comfyOnline = false,
  comfyRunning = false,
  webuiOnline = false,
  webuiRunning = false,
  isGenerating = false,
}) => {
  const { activeView, isRailCollapsed, setActiveView, toggleRail } = useNavigationStore();

  const getEngineStatus = (id: ViewType) => {
    if (id === 'comfyui') {
      return { isRunning: comfyRunning || comfyOnline, isGenerating };
    }
    if (id === 'webui') {
      return { isRunning: webuiRunning || webuiOnline, isGenerating: false };
    }
    return { isRunning: false, isGenerating: false };
  };

  const renderNavItem = (item: NavItem) => {
    const isActive = activeView === item.id;
    const Icon = item.icon;
    const status = item.isEngine ? getEngineStatus(item.id) : null;

    return (
      <button
        key={item.id}
        onClick={() => setActiveView(item.id)}
        title={isRailCollapsed ? item.label : undefined}
        className={`group relative flex items-center w-full px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
          isActive
            ? 'bg-slate-800 text-white font-semibold shadow-inner'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
        }`}
      >
        {/* Left accent bar for active item */}
        {isActive && (
          <span className="absolute left-0 top-1.5 bottom-1.5 w-1 bg-indigo-500 rounded-r" />
        )}

        {/* Icon with relative badge container */}
        <div className="relative flex items-center justify-center w-6 h-6 flex-shrink-0">
          <Icon className={`w-5 h-5 transition-transform duration-150 ${isActive ? 'text-indigo-400' : 'group-hover:scale-110'}`} />

          {/* Engine running indicator badge */}
          {status && status.isRunning && (
            <span
              className={`absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full ring-2 ring-slate-950 ${
                status.isGenerating ? 'bg-amber-400 animate-ping' : 'bg-emerald-500'
              }`}
            />
          )}
        </div>

        {/* Label (visible when expanded) */}
        {!isRailCollapsed && (
          <span className="ml-3 truncate tracking-wide text-xs">
            {item.label}
          </span>
        )}

        {/* Tooltip on hover when collapsed */}
        {isRailCollapsed && (
          <div className="absolute left-full ml-2 px-2 py-1 bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded shadow-lg opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-150 z-50 whitespace-nowrap">
            {item.label}
            {status?.isRunning && <span className="ml-1.5 text-emerald-400 font-semibold">(Running)</span>}
          </div>
        )}
      </button>
    );
  };

  return (
    <aside
      className={`flex flex-col justify-between bg-slate-900/90 border-r border-white/[0.08] backdrop-blur-md select-none transition-all duration-200 z-40 ${
        isRailCollapsed ? 'w-14' : 'w-48'
      }`}
    >
      {/* Top section: Toggle button & Main nav */}
      <div className="flex flex-col p-2 space-y-1">
        {/* Rail expand/collapse button */}
        <button
          onClick={toggleRail}
          aria-label={isRailCollapsed ? 'Expand navigation rail' : 'Collapse navigation rail'}
          className="flex items-center justify-center w-full h-9 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 transition-colors mb-2"
        >
          {isRailCollapsed ? (
            <Menu className="w-5 h-5" />
          ) : (
            <div className="flex items-center justify-between w-full px-2">
              <span className="text-xs font-bold text-slate-300 tracking-wider uppercase">Workspace</span>
              <ChevronLeft className="w-4 h-4 text-slate-400" />
            </div>
          )}
        </button>

        {/* Main Workspace Navigation */}
        <nav className="flex flex-col space-y-1">
          {mainNavItems.map(renderNavItem)}
        </nav>
      </div>

      {/* Bottom section: Settings & System */}
      <div className="p-2 border-t border-white/[0.06] space-y-1">
        {bottomNavItems.map(renderNavItem)}
      </div>
    </aside>
  );
};
