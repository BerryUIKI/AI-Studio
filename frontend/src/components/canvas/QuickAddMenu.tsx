import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Search,
  Sparkles,
  Image as ImageIcon,
  Type,
  Monitor,
  Upload,
  X,
  CornerDownLeft,
  Layers,
} from 'lucide-react';
import { NodeCategory, NodeDefinition } from '../../types/workflow';

// Fallback builtin nodes in case API is momentarily unavailable
const FALLBACK_NODES: NodeDefinition[] = [
  {
    type: 'image.generate',
    title: 'Cloud Image Generator',
    category: 'image',
    description: 'Generate high-fidelity images via cloud API (FLUX / SDXL)',
    inputs: [
      { id: 'prompt', name: 'Prompt', type: 'string', required: true },
      { id: 'ref_image', name: 'Reference Image', type: 'image', required: false },
    ],
    outputs: [{ id: 'image', name: 'Output Image', type: 'image' }],
    parameters: [
      {
        name: 'model',
        label: 'Model',
        type: 'select',
        default: 'flux-schnell',
        options: [
          { label: 'FLUX.1 [schnell] (Fast)', value: 'flux-schnell' },
          { label: 'FLUX.1 [dev] (High Quality)', value: 'flux-dev' },
          { label: 'SDXL Turbo', value: 'sdxl-turbo' },
        ],
      },
      {
        name: 'aspect_ratio',
        label: 'Aspect Ratio',
        type: 'select',
        default: '1:1',
        options: [
          { label: '1:1 Square', value: '1:1' },
          { label: '16:9 Landscape', value: '16:9' },
          { label: '9:16 Portrait (Shorts)', value: '9:16' },
          { label: '4:3 Standard', value: '4:3' },
        ],
      },
    ],
  },
  {
    type: 'text.llm',
    title: 'LLM Prompt Expander',
    category: 'text',
    description: 'Generate or refine text using OpenAI/DeepSeek compatible LLMs',
    inputs: [
      { id: 'prompt', name: 'Prompt', type: 'string', required: true },
      { id: 'system_prompt', name: 'System Instruction', type: 'string', required: false },
    ],
    outputs: [{ id: 'result', name: 'Generated Text', type: 'string' }],
    parameters: [
      {
        name: 'model',
        label: 'Model',
        type: 'select',
        default: 'deepseek-chat',
        options: [
          { label: 'DeepSeek Chat (V3)', value: 'deepseek-chat' },
          { label: 'GPT-4o Mini', value: 'gpt-4o-mini' },
          { label: 'GPT-4o', value: 'gpt-4o' },
          { label: 'Claude 3.5 Sonnet', value: 'claude-3-5-sonnet' },
        ],
      },
      {
        name: 'temperature',
        label: 'Creativity (Temperature)',
        type: 'number',
        default: 0.7,
        min_value: 0.0,
        max_value: 2.0,
        step: 0.1,
      },
    ],
  },
  {
    type: 'input.text',
    title: 'Text Input',
    category: 'input',
    description: 'Raw text or prompt input block',
    inputs: [],
    outputs: [{ id: 'text', name: 'Text Output', type: 'string' }],
    parameters: [
      {
        name: 'value',
        label: 'Prompt / Text',
        type: 'textarea',
        default: '',
        description: 'Enter text or prompt',
      },
    ],
  },
  {
    type: 'image.comfy.txt2img',
    title: 'Local ComfyUI Txt2Img',
    category: 'image',
    description: 'Generate images locally via sandboxed or external ComfyUI (No GPU cloud cost)',
    inputs: [
      { id: 'prompt', name: 'Prompt', type: 'string', required: true },
      { id: 'negative_prompt', name: 'Negative Prompt', type: 'string', required: false },
    ],
    outputs: [{ id: 'image', name: 'Output Image', type: 'image' }],
    parameters: [
      {
        name: 'checkpoint',
        label: 'Model Checkpoint',
        type: 'string',
        default: 'v1-5-pruned-emaonly.safetensors',
      },
      {
        name: 'steps',
        label: 'Inference Steps',
        type: 'number',
        default: 20,
      },
      {
        name: 'cfg',
        label: 'CFG Scale',
        type: 'number',
        default: 7.0,
      },
    ],
  },
  {
    type: 'output.preview',
    title: 'Media Preview',
    category: 'output',
    description: 'Inspect and preview text, image, or video outputs',
    inputs: [{ id: 'media', name: 'Media Input', type: 'image', required: true }],
    outputs: [],
    parameters: [],
  },
];

interface QuickAddMenuProps {
  isOpen: boolean;
  screenPosition: { x: number; y: number };
  flowPosition: { x: number; y: number };
  onClose: () => void;
  onSelectNode: (node: NodeDefinition, position: { x: number; y: number }) => void;
  onImportImage?: (position: { x: number; y: number }) => void;
}

export function QuickAddMenu({
  isOpen,
  screenPosition,
  flowPosition,
  onClose,
  onSelectNode,
  onImportImage,
}: QuickAddMenuProps) {
  const [nodes, setNodes] = useState<NodeDefinition[]>(FALLBACK_NODES);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedIndex, setSelectedIndex] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Fetch available nodes from backend on mount
  useEffect(() => {
    fetch('/api/v1/nodes')
      .then((res) => {
        if (res.ok) return res.json();
        throw new Error('Failed to load nodes');
      })
      .then((data: NodeDefinition[]) => {
        if (Array.isArray(data) && data.length > 0) {
          setNodes(data);
        }
      })
      .catch((err) => {
        console.warn('Using fallback node definitions:', err);
      });
  }, []);

  // Reset state when menu opens
  useEffect(() => {
    if (isOpen) {
      setSearch('');
      setSelectedCategory('all');
      setSelectedIndex(0);
      // Give DOM time to mount then focus
      setTimeout(() => {
        searchInputRef.current?.focus();
      }, 50);
    }
  }, [isOpen]);

  // Click outside to close
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as HTMLElement)) {
        onClose();
      }
    };

    window.addEventListener('mousedown', handleClickOutside, true);
    return () => window.removeEventListener('mousedown', handleClickOutside, true);
  }, [isOpen, onClose]);

interface QuickAddItem {
  key: string;
  title: string;
  category: NodeCategory;
  description: string;
  isAction: boolean;
  action: () => void;
}

  // Special creative action items
  const creativeActions: QuickAddItem[] = useMemo(() => {
    if (!onImportImage) return [];
    return [
      {
        key: 'action_import_image',
        title: 'Import Image Card',
        category: 'image',
        description: 'Upload an image file directly to this canvas coordinate',
        isAction: true,
        action: () => onImportImage(flowPosition),
      },
    ];
  }, [onImportImage, flowPosition]);

  // Filtered items
  const filteredItems: QuickAddItem[] = useMemo(() => {
    const q = search.trim().toLowerCase();

    // Map regular nodes
    const nodeItems: QuickAddItem[] = nodes.map((node) => ({
      key: node.type,
      title: node.title,
      category: node.category,
      description: node.description,
      isAction: false,
      action: () => onSelectNode(node, flowPosition),
    }));

    const allItems: QuickAddItem[] = [...creativeActions, ...nodeItems];

    return allItems.filter((item) => {
      // Category filter
      if (selectedCategory !== 'all' && item.category !== selectedCategory) {
        return false;
      }
      // Query filter
      if (!q) return true;
      return (
        item.title.toLowerCase().includes(q) ||
        item.description.toLowerCase().includes(q) ||
        item.category.toLowerCase().includes(q)
      );
    });
  }, [nodes, creativeActions, search, selectedCategory, onSelectNode, flowPosition]);

  // Keep selected index in bounds
  useEffect(() => {
    if (selectedIndex >= filteredItems.length) {
      setSelectedIndex(Math.max(0, filteredItems.length - 1));
    }
  }, [filteredItems.length, selectedIndex]);

  // Scroll active item into view
  useEffect(() => {
    if (!listRef.current) return;
    const activeEl = listRef.current.children[selectedIndex] as HTMLElement;
    if (activeEl) {
      activeEl.scrollIntoView({ block: 'nearest' });
    }
  }, [selectedIndex]);

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, filteredItems.length));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filteredItems.length) % Math.max(1, filteredItems.length));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredItems[selectedIndex]) {
        filteredItems[selectedIndex].action();
        onClose();
      }
    }
  };

  if (!isOpen) return null;

  // Viewport bounds clamping
  const MENU_WIDTH = 340;
  const MENU_MAX_HEIGHT = 440;
  const left = Math.max(16, Math.min(screenPosition.x, window.innerWidth - MENU_WIDTH - 16));
  const top = Math.max(16, Math.min(screenPosition.y, window.innerHeight - MENU_MAX_HEIGHT - 16));

  const getCategoryIcon = (category: string, isAction?: boolean) => {
    if (isAction) return Upload;
    switch (category) {
      case 'image':
        return ImageIcon;
      case 'text':
        return Sparkles;
      case 'input':
        return Type;
      case 'output':
        return Monitor;
      default:
        return Layers;
    }
  };

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'image':
        return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
      case 'text':
        return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
      case 'input':
        return 'text-sky-400 bg-sky-500/10 border-sky-500/20';
      case 'output':
        return 'text-purple-400 bg-purple-500/10 border-purple-500/20';
      default:
        return 'text-slate-400 bg-slate-500/10 border-slate-500/20';
    }
  };

  const categories = [
    { id: 'all', label: 'All' },
    { id: 'image', label: 'Image' },
    { id: 'text', label: 'Text' },
    { id: 'input', label: 'Input' },
    { id: 'output', label: 'Output' },
  ];

  return (
    <div
      ref={containerRef}
      onKeyDown={handleKeyDown}
      style={{ left, top, width: MENU_WIDTH }}
      className="fixed z-50 rounded-2xl bg-slate-900/95 border border-slate-700/80 shadow-2xl backdrop-blur-xl flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-100 select-none"
    >
      {/* Search Header */}
      <div className="p-2.5 border-b border-slate-800 flex items-center gap-2">
        <Search className="w-4 h-4 text-slate-400 shrink-0 ml-1" />
        <input
          ref={searchInputRef}
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search nodes or actions..."
          className="flex-1 bg-transparent text-xs text-slate-100 placeholder-slate-400 focus:outline-none"
        />
        {search && (
          <button
            onClick={() => setSearch('')}
            className="p-1 rounded-md text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
        <kbd className="text-[10px] text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700 font-mono">
          Esc
        </kbd>
      </div>

      {/* Category Filter Pills */}
      <div className="flex items-center gap-1 px-2.5 py-1.5 border-b border-slate-800/80 overflow-x-auto no-scrollbar">
        {categories.map((cat) => (
          <button
            key={cat.id}
            onClick={() => {
              setSelectedCategory(cat.id);
              setSelectedIndex(0);
            }}
            className={`px-2 py-0.5 rounded-full text-[11px] font-medium transition ${
              selectedCategory === cat.id
                ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Filtered Nodes List */}
      <div
        ref={listRef}
        className="max-h-[300px] overflow-y-auto p-1.5 space-y-1 divide-y divide-slate-800/40"
      >
        {filteredItems.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-400">
            No matching nodes or actions
          </div>
        ) : (
          filteredItems.map((item, idx) => {
            const isSelected = idx === selectedIndex;
            const Icon = getCategoryIcon(item.category, item.isAction);
            const colorClass = getCategoryColor(item.category);

            return (
              <button
                key={item.key}
                onClick={() => {
                  item.action();
                  onClose();
                }}
                onMouseEnter={() => setSelectedIndex(idx)}
                className={`w-full text-left p-2 rounded-xl transition flex items-center gap-2.5 group ${
                  isSelected
                    ? 'bg-indigo-600/20 text-indigo-200 ring-1 ring-indigo-500/40'
                    : 'text-slate-300 hover:bg-slate-800/60'
                }`}
              >
                {/* Icon Badge */}
                <div
                  className={`w-7 h-7 rounded-lg border flex items-center justify-center shrink-0 ${colorClass}`}
                >
                  <Icon className="w-3.5 h-3.5" />
                </div>

                {/* Details */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold tracking-tight truncate">
                      {item.title}
                    </span>
                    <span className="text-[9px] uppercase tracking-wider text-slate-400 font-medium">
                      {item.category}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 line-clamp-1 leading-snug">
                    {item.description}
                  </p>
                </div>

                {/* Enter shortcut icon */}
                {isSelected && (
                  <CornerDownLeft className="w-3.5 h-3.5 text-indigo-400 shrink-0 opacity-80" />
                )}
              </button>
            );
          })
        )}
      </div>

      {/* Footer Navigation Bar */}
      <div className="px-3 py-1.5 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between text-[10px] text-slate-400">
        <span className="flex items-center gap-1">
          <kbd className="px-1 rounded bg-slate-800 border border-slate-700 font-mono">↑↓</kbd>
          <span>Navigate</span>
          <kbd className="px-1 ml-1 rounded bg-slate-800 border border-slate-700 font-mono">↵</kbd>
          <span>Select</span>
        </span>
        <span>Right-click or Double-click</span>
      </div>
    </div>
  );
}
