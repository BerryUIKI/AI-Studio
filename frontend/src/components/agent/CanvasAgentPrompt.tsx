import { useState } from 'react';
import { Bot, X, CornerDownLeft } from 'lucide-react';
import { useCanvasStore } from '../../stores/useCanvasStore';
import { useCreativeStore } from '../../stores/useCreativeStore';

interface CanvasAgentPromptProps {
  isOpen: boolean;
  position: { x: number; y: number };
  flowPosition: { x: number; y: number };
  onClose: () => void;
}

export const CanvasAgentPrompt: React.FC<CanvasAgentPromptProps> = ({
  isOpen,
  position,
  flowPosition,
  onClose,
}) => {
  const [prompt, setPrompt] = useState('');
  const [mode, setMode] = useState<'workspace' | 'generate'>('workspace');
  const { addWorkspaceFrame } = useCanvasStore();
  const { executeCreativeAction } = useCreativeStore();

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    onClose();

    if (mode === 'workspace') {
      // 1. Create a bounded workspace frame at the target canvas location
      addWorkspaceFrame(prompt, flowPosition, { width: 780, height: 480 });

      // 2. Trigger generation of creative concepts within the workspace
      executeCreativeAction({
        prompt: prompt,
        action: 'txt2img',
      });
    } else {
      executeCreativeAction({
        prompt: prompt,
        action: 'txt2img',
      });
    }

    setPrompt('');
  };

  return (
    <div
      className="fixed z-50 animate-in fade-in zoom-in-95 duration-150"
      style={{ left: position.x, top: position.y }}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="bg-slate-900/95 backdrop-blur-xl border border-indigo-500/50 rounded-2xl p-3 shadow-2xl shadow-indigo-950/60 w-96 flex flex-col gap-2.5">
        <div className="flex items-center justify-between text-xs pb-1 border-b border-slate-800">
          <div className="flex items-center gap-1.5 text-indigo-300 font-medium">
            <Bot className="w-3.5 h-3.5 text-indigo-400" />
            <span>Spatial Agent Quick Assist</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-2">
          <div className="relative">
            <input
              type="text"
              autoFocus
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="What creative concepts should the agent explore?..."
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition pr-8"
            />
            <button
              type="submit"
              disabled={!prompt.trim()}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-indigo-400 disabled:opacity-30"
            >
              <CornerDownLeft className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-1 cursor-pointer">
                <input
                  type="radio"
                  name="agent-mode"
                  checked={mode === 'workspace'}
                  onChange={() => setMode('workspace')}
                  className="accent-indigo-500"
                />
                <span className="text-slate-300">Create Workspace Frame</span>
              </label>
            </div>
            <span className="text-[10px] text-slate-500 font-mono">Press Enter ↵</span>
          </div>
        </form>
      </div>
    </div>
  );
};
