import { useEffect, useState } from 'react';
import { Plus, Type, Image as ImageIcon, Sparkles, Monitor } from 'lucide-react';
import { NodeDefinition, NodeCategory } from '../../types/workflow';
import { useCanvasStore } from '../../stores/useCanvasStore';

const CATEGORY_ICONS: Record<string, any> = {
  input: Type,
  text: Sparkles,
  image: ImageIcon,
  output: Monitor,
};

export function NodePalette() {
  const [nodes, setNodes] = useState<NodeDefinition[]>([]);
  const addNode = useCanvasStore((state) => state.addNode);

  useEffect(() => {
    fetch('/api/v1/nodes')
      .then((res) => res.json())
      .then((data: NodeDefinition[]) => setNodes(data))
      .catch((err) => console.error('Failed to fetch node library:', err));
  }, []);

  const categories: NodeCategory[] = ['input', 'text', 'image', 'output'];

  return (
    <aside className="w-64 border-r border-slate-800/80 bg-slate-900/60 backdrop-blur-md flex flex-col h-full z-10 select-none">
      <div className="p-3.5 border-b border-slate-800 flex items-center justify-between">
        <h2 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Node Palette</h2>
        <span className="text-[10px] text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">
          {nodes.length} Nodes
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {categories.map((cat) => {
          const catNodes = nodes.filter((n) => n.category === cat);
          if (catNodes.length === 0) return null;
          const Icon = CATEGORY_ICONS[cat] || Sparkles;

          return (
            <div key={cat} className="space-y-1.5">
              <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wide px-1">
                <Icon className="w-3.5 h-3.5 text-indigo-400" />
                <span>{cat}</span>
              </div>
              <div className="space-y-1">
                {catNodes.map((node) => (
                  <button
                    key={node.type}
                    onClick={() => addNode(node)}
                    className="w-full text-left px-2.5 py-2 rounded-lg bg-slate-800/40 hover:bg-indigo-600/10 border border-slate-800 hover:border-indigo-500/30 transition flex items-center justify-between group"
                  >
                    <div>
                      <div className="text-xs font-medium text-slate-200 group-hover:text-indigo-300">
                        {node.title}
                      </div>
                      <div className="text-[10px] text-slate-400 line-clamp-1">
                        {node.description}
                      </div>
                    </div>
                    <Plus className="w-3.5 h-3.5 text-slate-400 group-hover:text-indigo-400 opacity-0 group-hover:opacity-100 transition" />
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
