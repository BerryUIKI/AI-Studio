import React, { useState } from 'react';
import { X, Settings, ShieldCheck, Check } from 'lucide-react';
import { EngineInstance } from '../../stores/useEngineStore';

interface EngineConfigModalProps {
  isOpen: boolean;
  instance: EngineInstance | null;
  onClose: () => void;
  onSave?: (instanceId: string, config: { port: number; extraArgs: string[] }) => void;
}

export const EngineConfigModal: React.FC<EngineConfigModalProps> = ({
  isOpen,
  instance,
  onClose,
  onSave,
}) => {
  const [port, setPort] = useState<number>(instance?.type === 'webui' ? 7860 : 8188);
  const [selectedFlags, setSelectedFlags] = useState<string[]>(['--lowvram']);
  const [customArgs, setCustomArgs] = useState<string>('');
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);

  if (!isOpen || !instance) return null;

  const toggleFlag = (flag: string) => {
    setSelectedFlags((prev) =>
      prev.includes(flag) ? prev.filter((f) => f !== flag) : [...prev, flag]
    );
  };

  const handleSave = () => {
    const allArgs = [...selectedFlags];
    if (customArgs.trim()) {
      allArgs.push(...customArgs.trim().split(/\s+/));
    }

    if (onSave) {
      onSave(instance.id, { port, extraArgs: allArgs });
    }

    setSavedSuccess(true);
    setTimeout(() => {
      setSavedSuccess(false);
      onClose();
    }, 800);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 select-none animate-in fade-in duration-150">
      <div className="relative w-full max-w-md rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl text-slate-100 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center space-x-2">
            <Settings className="w-5 h-5 text-indigo-400" />
            <h2 className="text-sm font-bold text-white">Configure {instance.name}</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Form */}
        <div className="p-6 space-y-4 text-xs">
          <div>
            <label className="block text-slate-300 font-medium mb-1">Port</label>
            <input
              type="number"
              value={port}
              onChange={(e) => setPort(parseInt(e.target.value) || 8188)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
            />
            <p className="text-[11px] text-slate-500 mt-1">Default: 8188 for ComfyUI, 7860 for WebUI</p>
          </div>

          <div>
            <label className="block text-slate-300 font-medium mb-2">Performance Optimization Flags</label>
            <div className="grid grid-cols-2 gap-2">
              {[
                { flag: '--lowvram', label: 'Low VRAM Mode' },
                { flag: '--medvram', label: 'Medium VRAM' },
                { flag: '--xformers', label: 'xFormers Attention' },
                { flag: '--cpu', label: 'CPU Inference Only' },
              ].map(({ flag, label }) => {
                const isSelected = selectedFlags.includes(flag);
                return (
                  <button
                    key={flag}
                    type="button"
                    onClick={() => toggleFlag(flag)}
                    className={`flex items-center justify-between p-2.5 rounded-xl border text-left transition-colors ${
                      isSelected
                        ? 'bg-indigo-600/10 border-indigo-500 text-indigo-300'
                        : 'bg-slate-800/40 border-slate-700/60 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <div>
                      <div className="font-semibold text-[11px]">{label}</div>
                      <div className="font-mono text-[10px] text-slate-500">{flag}</div>
                    </div>
                    {isSelected && <Check className="w-3.5 h-3.5 text-indigo-400" />}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-slate-300 font-medium mb-1">Custom Launch Arguments</label>
            <input
              type="text"
              value={customArgs}
              onChange={(e) => setCustomArgs(e.target.value)}
              placeholder="e.g. --listen 0.0.0.0 --fast"
              className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 font-mono"
            />
          </div>

          {savedSuccess && (
            <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4" />
              <span>Configuration saved successfully.</span>
            </div>
          )}

          <div className="pt-3 flex justify-end space-x-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg transition-colors"
            >
              Save Configuration
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
