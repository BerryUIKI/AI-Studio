import React, { useState } from 'react';
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

export const CreationDock = () => {
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
    engineId,
    setEngineId,
    model,
    setModel,
    referenceImage,
    setReferenceImage,
    seed,
    setSeed,
    randomizeSeed,
    isGenerating,
    generationStage,
    generationProgress,
    error,
    executeCreativeAction,
  } = useCreativeStore();

  const [showAdvanced, setShowAdvanced] = useState(false);

  const aspectRatios = ['1:1', '16:9', '9:16', '4:3'];

  const isCustomized =
    steps !== 20 ||
    cfgScale !== 7.0 ||
    Boolean(negativePrompt && negativePrompt !== 'low quality, blurry, deformed, bad anatomy') ||
    (referenceImage && denoise !== 0.75);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isGenerating) return;
    executeCreativeAction();
  };

  return (
    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 w-full max-w-3xl px-4 pointer-events-none">
      <div className="bg-slate-900/95 backdrop-blur-2xl border border-slate-800/90 rounded-2xl p-3 shadow-2xl shadow-slate-950/80 pointer-events-auto flex flex-col gap-2.5">
        {/* Error message if any */}
        {error && (
          <div className="px-3 py-1.5 rounded-lg bg-rose-950/60 border border-rose-800/50 text-rose-300 text-xs flex items-center justify-between">
            <span>{error}</span>
            <button
              onClick={() => useCreativeStore.setState({ error: null })}
              className="text-rose-400 hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Live Generation Stage Indicator (Issue #37) */}
        {isGenerating && (
          <div className="flex items-center justify-between px-3.5 py-2 rounded-xl bg-indigo-950/50 border border-indigo-800/60 text-xs animate-in fade-in">
            <div className="flex items-center gap-2.5">
              <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
              <div className="flex flex-col">
                <span className="font-medium text-indigo-200">{generationStage || 'Processing generative inference...'}</span>
                <span className="text-[10px] text-slate-400">Deterministic dirty-check verified</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-24 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-indigo-500 h-full rounded-full transition-all duration-300"
                  style={{ width: `${generationProgress || 20}%` }}
                />
              </div>
              <span className="text-[11px] font-mono text-indigo-300">{generationProgress}%</span>
            </div>
          </div>
        )}

        {/* Reference Image Badge (Img2Img Mode) */}
        {referenceImage && (
          <div className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-indigo-950/40 border border-indigo-800/50 text-xs">
            <div className="flex items-center gap-2">
              <img
                src={referenceImage.imageUrl}
                alt="Reference"
                className="w-7 h-7 rounded object-cover border border-indigo-700/50"
              />
              <div>
                <span className="font-medium text-indigo-300">Image-to-Image Variation</span>
                <p className="text-[10px] text-slate-400">Transforming selected canvas image</p>
              </div>
            </div>
            <button
              onClick={() => setReferenceImage(null)}
              className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              title="Clear reference"
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
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={
                referenceImage
                  ? 'Describe how to vary this image...'
                  : 'What do you want to create? (e.g. serene mountain cabin, oil painting...)'
              }
              className="w-full bg-slate-950/80 border border-slate-700/70 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition pr-10"
              disabled={isGenerating}
            />
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="submit"
              disabled={!prompt.trim() || isGenerating}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium shadow-lg shadow-indigo-600/25 transition whitespace-nowrap"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Creating...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>{referenceImage ? 'Vary Image' : 'Generate Image'}</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() =>
                executeCreativeAction({ action: referenceImage ? 'img2video' : 'txt2video' })
              }
              disabled={!prompt.trim() || isGenerating}
              className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-purple-600/90 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium shadow-lg shadow-purple-600/25 transition whitespace-nowrap"
              title="Generate Video (Text-to-Video or Image-to-Video)"
            >
              <Video className="w-4 h-4" />
              <span>Video</span>
            </button>
          </div>
        </form>

        {/* Primary Controls Toolbar: Aspect Ratio, Quick Engine & Advanced Toggle */}
        <div className="flex flex-wrap items-center justify-between text-xs pt-1 border-t border-slate-800/60 px-1 gap-2">
          {/* Aspect Ratios */}
          <div className="flex items-center gap-1">
            <span className="text-slate-400 mr-1 text-[11px]">Ratio:</span>
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
            <span className="text-slate-400 text-[11px]">Engine:</span>
            <select
              value={engineId}
              onChange={(e) => setEngineId(e.target.value)}
              className="bg-slate-800/90 border border-slate-700 rounded-md px-2 py-0.5 text-[11px] text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="managed_comfyui">ComfyUI (Local)</option>
              <option value="managed_webui">SD WebUI (Local)</option>
              <option value="cloud">Cloud API (Zero GPU)</option>
            </select>

            {/* Quick Models Inventory Link */}
            <button
              type="button"
              onClick={() => {
                window.location.hash = 'manager';
              }}
              title="Inspect local models, scan roots, and engine compatibility"
              className="px-2 py-0.5 rounded-md bg-purple-950/60 hover:bg-purple-900/80 text-purple-300 hover:text-purple-100 border border-purple-800/60 transition text-[11px] font-medium"
            >
              Models ↗
            </button>

            {/* Seed Randomizer */}
            <button
              type="button"
              onClick={randomizeSeed}
              title={`Seed: ${seed === -1 ? 'Random' : seed}. Click to randomize.`}
              className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/60 transition text-[11px]"
            >
              <Dices className="w-3.5 h-3.5 text-indigo-400" />
              <span>{seed === -1 ? 'Random' : seed}</span>
            </button>

            {/* Advanced Drawer Toggle (Issue #34 Progressive Disclosure) */}
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className={`flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium border transition ${
                showAdvanced || isCustomized
                  ? 'bg-indigo-600/30 border-indigo-500/60 text-indigo-200'
                  : 'bg-slate-800/80 border-slate-700/60 text-slate-400 hover:text-slate-200'
              }`}
              title="Toggle Advanced Parameters (CFG, Steps, Denoise, Negative Prompt)"
            >
              <SlidersHorizontal className="w-3 h-3" />
              <span>Advanced</span>
              {showAdvanced ? (
                <ChevronUp className="w-3 h-3" />
              ) : (
                <ChevronDown className="w-3 h-3" />
              )}
            </button>
          </div>
        </div>

        {/* Progressive Disclosure Advanced Controls Drawer (Issue #34) */}
        {showAdvanced && (
          <div className="pt-2.5 pb-1 border-t border-slate-800/70 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs animate-in slide-in-from-top-2 duration-150">
            {/* Negative Prompt */}
            <div className="flex flex-col gap-1 md:col-span-2">
              <label className="text-[11px] font-medium text-slate-300">
                Negative Prompt (What to exclude):
              </label>
              <input
                type="text"
                value={negativePrompt}
                onChange={(e) => setNegativePrompt(e.target.value)}
                placeholder="e.g. low quality, blurry, deformed..."
                className="w-full bg-slate-950/80 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* CFG Scale Slider */}
            <div className="flex flex-col gap-1 bg-slate-950/40 p-2 rounded-xl border border-slate-800/80">
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-slate-300 font-medium">CFG Scale (Prompt Guidance)</span>
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
                Higher = strictly adheres to prompt, lower = more creative freedom
              </span>
            </div>

            {/* Inference Steps Slider */}
            <div className="flex flex-col gap-1 bg-slate-950/40 p-2 rounded-xl border border-slate-800/80">
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-slate-300 font-medium">Sampling Steps</span>
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
                Standard: 20 steps. Higher increases quality but requires more time.
              </span>
            </div>

            {/* Denoise Strength (shown if img2img) */}
            {referenceImage && (
              <div className="flex flex-col gap-1 bg-slate-950/40 p-2 rounded-xl border border-slate-800/80">
                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-slate-300 font-medium">Denoising Strength</span>
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
                  0.3 = subtle touch-up, 0.75 = major variation, 1.0 = completely reimagined
                </span>
              </div>
            )}

            {/* Model Name Override */}
            <div className="flex flex-col gap-1 bg-slate-950/40 p-2 rounded-xl border border-slate-800/80">
              <label className="text-[11px] font-medium text-slate-300">Target Checkpoint / Model:</label>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="v1-5-pruned-emaonly.safetensors"
                className="w-full bg-slate-950 border border-slate-700 rounded-md px-2.5 py-1 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* Seed Configuration */}
            <div className="flex flex-col gap-1 bg-slate-950/40 p-2 rounded-xl border border-slate-800/80">
              <label className="text-[11px] font-medium text-slate-300">Seed (-1 for Random):</label>
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
                  Roll
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
