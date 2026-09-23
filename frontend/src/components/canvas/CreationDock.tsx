import { Dices, Sparkles, X, Loader2 } from 'lucide-react';
import { useCreativeStore } from '../../stores/useCreativeStore';

export const CreationDock = () => {
  const {
    prompt,
    setPrompt,
    aspectRatio,
    setAspectRatio,
    engineId,
    setEngineId,
    referenceImage,
    setReferenceImage,
    seed,
    randomizeSeed,
    isGenerating,
    error,
    executeCreativeAction,
  } = useCreativeStore();

  const aspectRatios = ['1:1', '16:9', '9:16', '4:3'];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isGenerating) return;
    executeCreativeAction();
  };

  return (
    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 w-full max-w-3xl px-4 pointer-events-none">
      <div className="bg-slate-900/90 backdrop-blur-xl border border-slate-800 rounded-2xl p-3 shadow-2xl pointer-events-auto flex flex-col gap-2.5">
        {/* Error message if any */}
        {error && (
          <div className="px-3 py-1.5 rounded-lg bg-rose-950/60 border border-rose-800/50 text-rose-300 text-xs flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => useCreativeStore.setState({ error: null })} className="text-rose-400 hover:text-white">
              <X className="w-3.5 h-3.5" />
            </button>
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

        {/* Prompt Input Form */}
        <form onSubmit={handleSubmit} className="flex items-center gap-2">
          <div className="relative flex-1">
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={referenceImage ? "Describe how to vary this image..." : "What do you want to create? (e.g. serene mountain cabin, oil painting...)"}
              className="w-full bg-slate-950/80 border border-slate-700/70 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition pr-10"
              disabled={isGenerating}
            />
          </div>

          <button
            type="submit"
            disabled={!prompt.trim() || isGenerating}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium shadow-lg shadow-indigo-600/25 transition whitespace-nowrap"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Creating...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>{referenceImage ? 'Vary Image' : 'Generate'}</span>
              </>
            )}
          </button>
        </form>

        {/* Controls Toolbar: Aspect Ratio, Engine, Seed */}
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

          {/* Engine Selector */}
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
          </div>
        </div>
      </div>
    </div>
  );
};
