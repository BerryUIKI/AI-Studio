import { useUiText } from '../../i18n/useUiText';
import { errorMessage as getErrorMessage } from '../../utils/errors';
import { Dialog } from '../ui/Dialog';
import React, { useState, useEffect } from 'react';
import { X, Settings, ShieldCheck, Check, AlertCircle, AlertTriangle, Loader2, Info } from 'lucide-react';
import { EngineInstance, SaveEngineConfigResult, useEngineStore } from '../../stores/useEngineStore';

interface EngineConfigModalProps {
  isOpen: boolean;
  instance: EngineInstance | null;
  onClose: () => void;
  onSave?: (
    instanceId: string,
    config: { port: number; extraArgs: string[] }
  ) => Promise<SaveEngineConfigResult | void> | void;
}

const KNOWN_FLAGS = [
  { flag: '--lowvram', label: 'Low VRAM Mode' },
  { flag: '--medvram', label: 'Medium VRAM' },
  { flag: '--xformers', label: 'xFormers Attention' },
  { flag: '--cpu', label: 'CPU Inference Only' },
];

export const EngineConfigModal: React.FC<EngineConfigModalProps> = ({
  isOpen,
  instance,
  onClose,
  onSave,
}) => {
  const ui = useUiText();
  const [port, setPort] = useState<string>('8188');
  const [selectedFlags, setSelectedFlags] = useState<string[]>(['--lowvram']);
  const [customArgs, setCustomArgs] = useState<string>('');
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);
  const [successMessage, setSuccessMessage] = useState<string>('');
  const [isRestartRequired, setIsRestartRequired] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Synchronize state whenever a new instance is selected or dialog opens
  useEffect(() => {
    if (!isOpen || !instance) {
      setSavedSuccess(false);
      setErrorMessage(null);
      setIsSaving(false);
      return;
    }

    // Determine initial port from instance
    let initialPort = instance.port;
    if (!initialPort && instance.endpoint) {
      try {
        const parsed = Number(new URL(instance.endpoint).port);
        if (parsed) initialPort = parsed;
      } catch {
        // Ignore URL parsing fallback
      }
    }
    if (!initialPort) {
      initialPort = instance.type === 'webui' ? 7860 : 8188;
    }

    const currentArgs = instance.extra_args || (instance.type === 'comfyui' ? ['--lowvram'] : []);
    const knownFlagStrings = KNOWN_FLAGS.map((f) => f.flag);
    const flags = currentArgs.filter((a) => knownFlagStrings.includes(a));
    const custom = currentArgs.filter((a) => !knownFlagStrings.includes(a)).join(' ');

    setPort(String(initialPort));
    setSelectedFlags(flags);
    setCustomArgs(custom);
    setSavedSuccess(false);
    setErrorMessage(null);
    setIsSaving(false);

    // Asynchronously fetch fresh backend configuration
    let cancelled = false;
    const fetchFreshConfig = async () => {
      const cfg = await useEngineStore.getState().fetchEngineConfig(instance.id);
      if (!cancelled && cfg) {
        setPort(String(cfg.port));
        const freshFlags = (cfg.extra_args || []).filter((a) => knownFlagStrings.includes(a));
        const freshCustom = (cfg.extra_args || []).filter((a) => !knownFlagStrings.includes(a)).join(' ');
        setSelectedFlags(freshFlags);
        setCustomArgs(freshCustom);
      }
    };
    fetchFreshConfig();

    return () => {
      cancelled = true;
    };
  }, [isOpen, instance?.id]);

  if (!isOpen || !instance) return null;

  const toggleFlag = (flag: string) => {
    setSelectedFlags((prev) =>
      prev.includes(flag) ? prev.filter((f) => f !== flag) : [...prev, flag]
    );
  };

  const handleSave = async () => {
    setErrorMessage(null);
    setSavedSuccess(false);

    const portNum = parseInt(port, 10);
    if (isNaN(portNum) || portNum < 1 || portNum > 65535) {
      setErrorMessage(ui("ui_port_must_be_a_valid_integer_between_1"));
      return;
    }

    const allArgs = [...selectedFlags];
    if (customArgs.trim()) {
      const customTokens = customArgs.trim().split(/\s+/);
      for (const token of customTokens) {
        if (!allArgs.includes(token)) {
          allArgs.push(token);
        }
      }
    }

    setIsSaving(true);
    try {
      let result: SaveEngineConfigResult | void;
      if (onSave) {
        result = await onSave(instance.id, { port: portNum, extraArgs: allArgs });
      } else {
        result = await useEngineStore.getState().saveEngineConfig(instance.id, {
          port: portNum,
          extraArgs: allArgs,
        });
      }

      if (result && result.success === false) {
        setErrorMessage(result.message || ui("ui_failed_to_save_engine_configuration"));
        return;
      }

      const restartRequired = Boolean(result?.requires_restart || instance.status === 'running');
      setIsRestartRequired(restartRequired);
      setSuccessMessage(
        result?.message ||
          (restartRequired
            ? ui("ui_configuration_saved_engine_restart_is_required_for_changes")
            : ui("ui_configuration_saved_successfully"))
      );
      setSavedSuccess(true);

      setTimeout(() => {
        setSavedSuccess(false);
        onClose();
      }, restartRequired ? 1400 : 900);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, ui("ui_an_unexpected_error_occurred_while_saving")));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog title={ui("ui_engine_configuration")} onClose={onClose} className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 select-none animate-in fade-in duration-150">
      <div className="relative w-full max-w-md rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl text-slate-100 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center space-x-2">
            <Settings className="w-5 h-5 text-indigo-400" />
            <h2 className="text-sm font-bold text-white">{ui("ui_configure")}{instance.name}</h2>
          </div>
          <button
            onClick={onClose}
            aria-label={ui("ui_close_dialog")}
            disabled={isSaving}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors disabled:opacity-50"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Form */}
        <div className="p-6 space-y-4 text-xs">
          {/* Running Status Notice */}
          {instance.status === 'running' && (
            <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 flex items-start space-x-2 text-[11px]">
              <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
              <div>
                <span className="font-semibold block">{ui("ui_engine_is_actively_running")}</span>
                <span>{ui("ui_port_and_launch_argument_changes_will_take_effect")}</span>
              </div>
            </div>
          )}

          {/* External Engine Protection Notice */}
          {!instance.is_managed && (
            <div className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 flex items-center space-x-2 text-[11px]">
              <Info className="w-4 h-4 shrink-0 text-indigo-400" />
              <span>{ui("ui_external_engine_berry_manages_connection_endpoints_only_zero")}</span>
            </div>
          )}

          <div>
            <label className="block text-slate-300 font-medium mb-1">{ui("ui_port")}</label>
            <input
              type="number"
              value={port}
              disabled={isSaving}
              onChange={(e) => setPort(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:border-indigo-500 font-mono disabled:opacity-50"
            />
            <p className="text-[11px] text-slate-500 mt-1">{ui("ui_default_8188_for_comfyui_7860_for_webui")}</p>
          </div>

          <div>
            <label className="block text-slate-300 font-medium mb-2">{ui("ui_performance_optimization_flags")}</label>
            <div className="grid grid-cols-2 gap-2">
              {KNOWN_FLAGS.map(({ flag, label }) => {
                const isSelected = selectedFlags.includes(flag);
                return (
                  <button
                    key={flag}
                    type="button"
                    disabled={isSaving}
                    onClick={() => toggleFlag(flag)}
                    className={`flex items-center justify-between p-2.5 rounded-xl border text-left transition-colors ${
                      isSelected
                        ? 'bg-indigo-600/10 border-indigo-500 text-indigo-300'
                        : 'bg-slate-800/40 border-slate-700/60 text-slate-400 hover:text-slate-200'
                    } disabled:opacity-50`}
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
            <label className="block text-slate-300 font-medium mb-1">{ui("ui_custom_launch_arguments")}</label>
            <input
              type="text"
              value={customArgs}
              disabled={isSaving}
              onChange={(e) => setCustomArgs(e.target.value)}
              placeholder={ui("ui_e_g_listen_0_0_0_0_fast")}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 font-mono disabled:opacity-50"
            />
          </div>

          {/* Error Banner */}
          {errorMessage && (
            <div className="p-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Success Banner */}
          {savedSuccess && (
            <div
              className={`p-2.5 rounded-lg flex items-center space-x-2 ${
                isRestartRequired
                  ? 'bg-amber-500/10 border border-amber-500/20 text-amber-300'
                  : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
              }`}
            >
              <ShieldCheck className="w-4 h-4 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          <div className="pt-3 flex justify-end space-x-2">
            <button
              type="button"
              disabled={isSaving}
              onClick={onClose}
            aria-label={ui("ui_close_dialog")}
              className="px-3.5 py-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors disabled:opacity-50"
            >
              {ui("ui_cancel")}</button>
            <button
              type="button"
              disabled={isSaving}
              onClick={handleSave}
              className="flex items-center space-x-1.5 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg transition-colors disabled:opacity-50"
            >
              {isSaving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>{isSaving ? ui("ui_saving_2") : ui("ui_save_configuration")}</span>
            </button>
          </div>
        </div>
      </div>
    </Dialog>
  );
};
