import { useUiText } from '../../i18n/useUiText';
import { useShallow } from 'zustand/react/shallow';
import React, { useState } from 'react';
import type { Node } from '@xyflow/react';
import {
  Dices,
  Sparkles,
  Video,
  X,
  Loader2,
  SlidersHorizontal,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { useCreativeStore } from '../../stores/useCreativeStore';
import { useCanvasStore } from '../../stores/useCanvasStore';
import { useNavigationStore } from '../../stores/useNavigationStore';
import type { ImageCardData } from '../../types/creative';
import { FloatingCardToolbar } from './FloatingCardToolbar';
import { CreationSetup, useCreationReadiness } from './CreationSetup';

import { CreativeTaskFeedback } from './CreativeTaskFeedback';
export { CreativeTaskStatus } from './CreativeTaskFeedback';

interface CreationDockProps {
  onCloudSetup?: () => void;
  onLocalSetup?: () => void;
  onOpenModels?: () => void;
}

export const CreationDock = ({ onCloudSetup = () => undefined, onLocalSetup = () => undefined,
  onOpenModels = () => useNavigationStore.getState().setActiveView('models') }: CreationDockProps) => {
  const ui = useUiText();
  const selectedImage = useCanvasStore((state) => state.nodes.find(
    (node): node is Node<ImageCardData> => node.id === state.selectedNodeId && node.type === 'imageCard',
  ));
  const {
    prompt,
    setPrompt,
    negativePrompt,
    setNegativePrompt,
    aspectRatio,
    setAspectRatio,
    steps,
    setSteps,
    cfgScale,
    setCfgScale,
    denoise,
    setDenoise,
    referenceImage,
    setReferenceImage,
    seed,
    setSeed,
    randomizeSeed,
    isGenerating,
    executeCreativeAction,
  } = useCreativeStore(useShallow((state) => ({
    prompt: state.prompt,
    setPrompt: state.setPrompt,
    negativePrompt: state.negativePrompt,
    setNegativePrompt: state.setNegativePrompt,
    aspectRatio: state.aspectRatio,
    setAspectRatio: state.setAspectRatio,
    steps: state.steps,
    setSteps: state.setSteps,
    cfgScale: state.cfgScale,
    setCfgScale: state.setCfgScale,
    denoise: state.denoise,
    setDenoise: state.setDenoise,
    referenceImage: state.referenceImage,
    setReferenceImage: state.setReferenceImage,
    seed: state.seed,
    setSeed: state.setSeed,
    randomizeSeed: state.randomizeSeed,
    isGenerating: state.isGenerating,
    executeCreativeAction: state.executeCreativeAction,
  })));

  const [showAdvanced, setShowAdvanced] = useState(false);
  const { ready, provider } = useCreationReadiness();

  const aspectRatios = ['1:1', '16:9', '9:16', '4:3'];

  const isCustomized =
    steps !== 20 ||
    cfgScale !== 7.0 ||
    Boolean(negativePrompt && negativePrompt !== 'low quality, blurry, deformed, bad anatomy') ||
    (referenceImage && denoise !== 0.75);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isGenerating || !ready) return;
    executeCreativeAction();
  };

  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 w-full max-w-3xl max-h-[70vh] overflow-y-auto px-4 pointer-events-none">
      <div className="bg-slate-900/95 backdrop-blur-2xl border border-slate-800/90 rounded-2xl p-3 shadow-2xl shadow-slate-950/80 pointer-events-auto flex flex-col gap-2.5">
        {selectedImage && !selectedImage.data.isGenerating && (
          <FloatingCardToolbar nodeId={selectedImage.id} data={selectedImage.data} />
        )}
        <CreativeTaskFeedback />
        <CreationSetup onCloudSetup={onCloudSetup} onLocalSetup={onLocalSetup} />

        {/* Reference Image Badge (Img2Img Mode) */}
        {referenceImage && (
          <div className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-indigo-950/40 border border-indigo-800/50 text-xs">
            <div className="flex items-center gap-2">
              <img
                src={referenceImage.imageUrl}
                alt={ui("ui_reference")}
                className="w-7 h-7 rounded object-cover border border-indigo-700/50"
              />
              <div>
                <span className="font-medium text-indigo-300">{ui("ui_image_to_image_variation")}</span>
                <p className="text-[10px] text-slate-400">{ui("ui_transforming_selected_canvas_image")}</p>
              </div>
            </div>
            <button
              onClick={() => setReferenceImage(null)}
              className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              title={ui("ui_clear_reference")}
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Primary Creation Form */}
        <form onSubmit={handleSubmit} className="flex items-center gap-2">
          <div className="relative flex-1">
            <input
              type="text"
              aria-label={ui("ui_image_prompt")}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={
                referenceImage
                  ? ui("ui_describe_how_to_vary_this_image")
                  : ui("ui_what_do_you_want_to_create_e_g")
              }
              className="w-full bg-slate-950/80 border border-slate-700/70 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition pr-10"
              disabled={isGenerating}
            />
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="submit"
              disabled={!prompt.trim() || isGenerating || !ready}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium shadow-lg shadow-indigo-600/25 transition whitespace-nowrap"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{ui("ui_creating")}</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>{referenceImage ? ui("ui_vary_image") : ui("ui_generate_image")}</span>
                </>
              )}
            </button>

            {showAdvanced && <button
              type="button"
              onClick={() =>
                executeCreativeAction({ action: referenceImage ? 'img2video' : 'txt2video' })
              }
              disabled={!prompt.trim() || isGenerating}
              className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-purple-600/90 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium shadow-lg shadow-purple-600/25 transition whitespace-nowrap"
              title={ui("ui_experimental_video_generation_integration_unverified")}
            >
              <Video className="w-4 h-4" />
              <span>{ui("ui_experimental_video")}</span>
            </button>}
          </div>
        </form>

        {/* Primary Controls Toolbar: Aspect Ratio, Quick Engine & Advanced Toggle */}
        <div className="flex flex-wrap items-center justify-between text-xs pt-1 border-t border-slate-800/60 px-1 gap-2">
          {/* Aspect Ratios */}
          <div className="flex items-center gap-1">
            <span className="text-slate-400 mr-1 text-[11px]">{ui("ui_ratio")}</span>
            {aspectRatios.map((ratio) => (
              <button
                key={ratio}
                type="button"
                onClick={() => setAspectRatio(ratio)}
                className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition ${
                  aspectRatio === ratio
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'bg-slate-800/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                {ratio}
              </button>
            ))}
          </div>

          {/* Quick Engine, Seed, and Advanced Toggle */}
          <div className="flex items-center gap-2">

            {/* Quick Models Inventory Link */}
            <button
              type="button"
              onClick={onOpenModels}
              title={ui("ui_inspect_local_models_scan_roots_and_engine_compatibility")}
              className="px-2 py-0.5 rounded-md bg-purple-950/60 hover:bg-purple-900/80 text-purple-300 hover:text-purple-100 border border-purple-800/60 transition text-[11px] font-medium"
            >
              {ui("ui_models")}</button>

            {/* Seed Randomizer */}
            <button
              type="button"
              onClick={randomizeSeed}
              title={provider ? ui("ui_new_variation") : ui("ui_seed_value_click_to_randomize", { value1: seed === -1 ? 'Random' : seed })}
              className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/60 transition text-[11px]"
            >
              <Dices className="w-3.5 h-3.5 text-indigo-400" />
              <span>{provider ? ui("ui_new_variation") : seed === -1 ? ui("ui_random") : seed}</span>
            </button>

            {/* Advanced Drawer Toggle (Issue #34 Progressive Disclosure) */}
            {!provider && <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className={`flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium border transition ${
                showAdvanced || isCustomized
                  ? 'bg-indigo-600/30 border-indigo-500/60 text-indigo-200'
                  : 'bg-slate-800/80 border-slate-700/60 text-slate-400 hover:text-slate-200'
              }`}
              title={ui("ui_toggle_advanced_parameters_cfg_steps_denoise_negative_prompt")}
            >
              <SlidersHorizontal className="w-3 h-3" />
              <span>{ui("ui_advanced")}</span>
              {showAdvanced ? (
                <ChevronUp className="w-3 h-3" />
              ) : (
                <ChevronDown className="w-3 h-3" />
              )}
            </button>}
          </div>
        </div>

        {/* Progressive Disclosure Advanced Controls Drawer (Issue #34) */}
        {showAdvanced && !provider && (
          <div className="pt-2.5 pb-1 border-t border-slate-800/70 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs animate-in slide-in-from-top-2 duration-150">
            {/* Negative Prompt */}
            <div className="flex flex-col gap-1 md:col-span-2">
              <label className="text-[11px] font-medium text-slate-300">
                {ui("ui_negative_prompt_what_to_exclude")}</label>
              <input
                type="text"
                value={negativePrompt}
                onChange={(e) => setNegativePrompt(e.target.value)}
                placeholder={ui("ui_e_g_low_quality_blurry_deformed")}
                className="w-full bg-slate-950/80 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* CFG Scale Slider */}
            <div className="flex flex-col gap-1 bg-slate-950/40 p-2 rounded-xl border border-slate-800/80">
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-slate-300 font-medium">{ui("ui_cfg_scale_prompt_guidance")}</span>
                <span className="font-mono text-indigo-400">{cfgScale}</span>
              </div>
              <input
                type="range"
                min="1"
                max="20"
                step="0.5"
                value={cfgScale}
                onChange={(e) => setCfgScale(parseFloat(e.target.value))}
                className="w-full accent-indigo-500 cursor-pointer"
              />
              <span className="text-[10px] text-slate-500">
                {ui("ui_higher_strictly_adheres_to_prompt_lower_more_creative")}</span>
            </div>

            {/* Inference Steps Slider */}
            <div className="flex flex-col gap-1 bg-slate-950/40 p-2 rounded-xl border border-slate-800/80">
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-slate-300 font-medium">{ui("ui_sampling_steps")}</span>
                <span className="font-mono text-indigo-400">{steps}</span>
              </div>
              <input
                type="range"
                min="10"
                max="50"
                step="1"
                value={steps}
                onChange={(e) => setSteps(parseInt(e.target.value, 10))}
                className="w-full accent-indigo-500 cursor-pointer"
              />
              <span className="text-[10px] text-slate-500">
                {ui("ui_standard_20_steps_higher_increases_quality_but_requires")}</span>
            </div>

            {/* Denoise Strength (shown if img2img) */}
            {referenceImage && (
              <div className="flex flex-col gap-1 bg-slate-950/40 p-2 rounded-xl border border-slate-800/80">
                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-slate-300 font-medium">{ui("ui_denoising_strength")}</span>
                  <span className="font-mono text-indigo-400">{denoise}</span>
                </div>
                <input
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.05"
                  value={denoise}
                  onChange={(e) => setDenoise(parseFloat(e.target.value))}
                  className="w-full accent-indigo-500 cursor-pointer"
                />
                <span className="text-[10px] text-slate-500">
                  {ui("ui_0_3_subtle_touch_up_0_75_major")}</span>
              </div>
            )}


            {/* Seed Configuration */}
            <div className="flex flex-col gap-1 bg-slate-950/40 p-2 rounded-xl border border-slate-800/80">
              <label className="text-[11px] font-medium text-slate-300">{ui("ui_seed_1_for_random")}</label>
              <div className="flex items-center gap-1.5">
                <input
                  type="number"
                  value={seed}
                  onChange={(e) => setSeed(parseInt(e.target.value, 10) || -1)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-md px-2.5 py-1 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
                />
                <button
                  type="button"
                  onClick={randomizeSeed}
                  className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-md text-xs whitespace-nowrap"
                >
                  {ui("ui_roll")}</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
