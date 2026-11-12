import { useUiText } from '../../i18n/useUiText';
import { Dialog } from '../ui/Dialog';
import { useState } from 'react';
import { Loader2, Maximize2, Sparkles, X } from 'lucide-react';
import { useCreativeStore } from '../../stores/useCreativeStore';
import { useCreationReadiness } from './CreationSetup';
import { CreativeTaskFeedback } from './CreativeTaskFeedback';

export const UpscaleModal = () => {
  const ui = useUiText();
  const { ready, provider } = useCreationReadiness('upscale');
  const { upscaleModalOpen, referenceImage, closeModals, executeCreativeAction, isGenerating } =
    useCreativeStore();
  const [scaleFactor, setScaleFactor] = useState<number>(2.0);
  const [upscalerName, setUpscalerName] = useState<string>('R-ESRGAN 4x+');
  const [naturalDim, setNaturalDim] = useState<{ width: number; height: number } | null>(null);

  if (!upscaleModalOpen || !referenceImage) return null;

  const currentW = (referenceImage.width && referenceImage.width > 0) ? referenceImage.width : (naturalDim?.width || 512);
  const currentH = (referenceImage.height && referenceImage.height > 0) ? referenceImage.height : (naturalDim?.height || 512);
  const targetW = Math.round(currentW * scaleFactor);
  const targetH = Math.round(currentH * scaleFactor);

  const handleUpscale = async () => {
    if (!referenceImage?.assetId || isGenerating || !ready) return;

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
    <Dialog title={ui("ui_upscale_image")} onClose={closeModals} className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md max-h-[90vh] shadow-2xl overflow-y-auto flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Maximize2 className="w-5 h-5 text-emerald-400" />
            <h2 className="font-semibold text-sm text-slate-100">{ui("ui_upscale_image_resolution")}</h2>
          </div>
          <button
            onClick={closeModals}
            aria-label={ui("ui_close_dialog")}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 flex flex-col gap-4">
          <CreativeTaskFeedback />
          {/* Image Thumbnail Preview */}
          <div className="flex items-center gap-4 bg-slate-950 p-3 rounded-xl border border-slate-800">
            <img
              src={referenceImage.imageUrl}
              alt={ui("ui_thumbnail")}
              className="w-16 h-16 rounded-lg object-cover border border-slate-700"
              onLoad={(e) => {
                const img = e.currentTarget;
                if ((!referenceImage.width || !referenceImage.height) && img.naturalWidth && img.naturalHeight) {
                  setNaturalDim({ width: img.naturalWidth, height: img.naturalHeight });
                }
              }}
            />
            <div className="flex flex-col text-xs">
              <span className="font-medium text-slate-200 line-clamp-1">{referenceImage.label || ui("ui_selected_asset")}</span>
              <span className="text-slate-400 mt-1" data-testid="source-dimensions">{ui("ui_current")}{currentW} × {currentH} {ui("ui_px")}</span>
              <span className="text-emerald-400 font-medium" data-testid="target-dimensions">{ui("ui_target")}{targetW} × {targetH} {ui("ui_px")}</span>
            </div>
          </div>

          {/* Upscale Factor Selection */}
          <div className="flex flex-col gap-1.5 text-xs">
            <span className="text-slate-300 font-medium">{ui("ui_scale_factor")}</span>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                data-testid="scale-factor-2x"
                onClick={() => setScaleFactor(2.0)}
                className={`py-2 px-3 rounded-xl border font-medium transition ${
                  scaleFactor === 2.0
                    ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300'
                    : 'bg-slate-800/80 border-slate-700 text-slate-400 hover:text-slate-200'
                }`}
              >
                {ui("ui_2_resolution")}</button>
              <button
                type="button"
                data-testid="scale-factor-4x"
                onClick={() => setScaleFactor(4.0)}
                className={`py-2 px-3 rounded-xl border font-medium transition ${
                  scaleFactor === 4.0
                    ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300'
                    : 'bg-slate-800/80 border-slate-700 text-slate-400 hover:text-slate-200'
                }`}
              >
                {ui("ui_4_resolution_ultra_hd")}</button>
            </div>
          </div>

          {/* Upscaler Model */}
          {!provider && <div className="flex flex-col gap-1.5 text-xs">
            <span className="text-slate-300 font-medium">{ui("ui_upscaler_algorithm")}</span>
            <select
              value={upscalerName}
              onChange={(e) => setUpscalerName(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="R-ESRGAN 4x+">{ui("ui_realesrgan_4x_photorealistic")}</option>
              <option value="4x-UltraSharp">{ui("ui_4x_ultrasharp_sharp_edges")}</option>
            </select>
          </div>}
        </div>

        {/* Footer Actions */}
        <div className="p-4 bg-slate-900 border-t border-slate-800 flex items-center justify-end gap-2">
          <button
            onClick={closeModals}
            aria-label={ui("ui_close_dialog")}
            className="px-4 py-2 rounded-xl text-xs font-medium text-slate-300 hover:bg-slate-800 transition"
          >
            {ui("ui_cancel")}</button>
          <button
            onClick={handleUpscale}
            disabled={isGenerating || !ready}
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-xs font-medium shadow-lg transition"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>{ui("ui_upscaling")}</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>{ui("ui_upscale_to")}{targetW}×{targetH}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </Dialog>
  );
};
