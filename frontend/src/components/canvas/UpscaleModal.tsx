import { useState } from 'react';
import { Loader2, Maximize2, Sparkles, X } from 'lucide-react';
import { useCreativeStore } from '../../stores/useCreativeStore';

export const UpscaleModal = () => {
  const { upscaleModalOpen, referenceImage, closeModals, executeCreativeAction, isGenerating } =
    useCreativeStore();
  const [scaleFactor, setScaleFactor] = useState<number>(2.0);
  const [upscalerName, setUpscalerName] = useState<string>('R-ESRGAN 4x+');

  if (!upscaleModalOpen || !referenceImage) return null;

  const currentW = referenceImage.width || 512;
  const currentH = referenceImage.height || 512;
  const targetW = Math.round(currentW * scaleFactor);
  const targetH = Math.round(currentH * scaleFactor);

  const handleUpscale = async () => {
    if (!referenceImage?.assetId || isGenerating) return;

    const res = await executeCreativeAction({
      action: 'upscale',
      input_image_id: referenceImage.assetId,
      upscale_factor: scaleFactor,
      upscaler_name: upscalerName,
      width: currentW,
      height: currentH,
    });

    if (res && res.success) {
      closeModals();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Maximize2 className="w-5 h-5 text-emerald-400" />
            <h2 className="font-semibold text-sm text-slate-100">Upscale Image Resolution</h2>
          </div>
          <button
            onClick={closeModals}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 flex flex-col gap-4">
          {/* Image Thumbnail Preview */}
          <div className="flex items-center gap-4 bg-slate-950 p-3 rounded-xl border border-slate-800">
            <img
              src={referenceImage.imageUrl}
              alt="Thumbnail"
              className="w-16 h-16 rounded-lg object-cover border border-slate-700"
            />
            <div className="flex flex-col text-xs">
              <span className="font-medium text-slate-200 line-clamp-1">{referenceImage.label || 'Selected Asset'}</span>
              <span className="text-slate-400 mt-1">Current: {currentW} × {currentH} px</span>
              <span className="text-emerald-400 font-medium">Target: {targetW} × {targetH} px</span>
            </div>
          </div>

          {/* Upscale Factor Selection */}
          <div className="flex flex-col gap-1.5 text-xs">
            <span className="text-slate-300 font-medium">Scale Factor:</span>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setScaleFactor(2.0)}
                className={`py-2 px-3 rounded-xl border font-medium transition ${
                  scaleFactor === 2.0
                    ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300'
                    : 'bg-slate-800/80 border-slate-700 text-slate-400 hover:text-slate-200'
                }`}
              >
                2× Resolution
              </button>
              <button
                type="button"
                onClick={() => setScaleFactor(4.0)}
                className={`py-2 px-3 rounded-xl border font-medium transition ${
                  scaleFactor === 4.0
                    ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300'
                    : 'bg-slate-800/80 border-slate-700 text-slate-400 hover:text-slate-200'
                }`}
              >
                4× Resolution (Ultra HD)
              </button>
            </div>
          </div>

          {/* Upscaler Model */}
          <div className="flex flex-col gap-1.5 text-xs">
            <span className="text-slate-300 font-medium">Upscaler Algorithm:</span>
            <select
              value={upscalerName}
              onChange={(e) => setUpscalerName(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="R-ESRGAN 4x+">RealESRGAN 4x+ (Photorealistic)</option>
              <option value="4x-UltraSharp">4x-UltraSharp (Sharp Edges)</option>
            </select>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 bg-slate-900 border-t border-slate-800 flex items-center justify-end gap-2">
          <button
            onClick={closeModals}
            className="px-4 py-2 rounded-xl text-xs font-medium text-slate-300 hover:bg-slate-800 transition"
          >
            Cancel
          </button>
          <button
            onClick={handleUpscale}
            disabled={isGenerating}
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-xs font-medium shadow-lg transition"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Upscaling...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Upscale to {targetW}×{targetH}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
