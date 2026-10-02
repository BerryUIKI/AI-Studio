import { useState } from 'react';
import { Clapperboard, Loader2, Video, X } from 'lucide-react';
import { useCreativeStore } from '../../stores/useCreativeStore';

export const VideoModal = () => {
  const {
    videoModalOpen,
    referenceImage,
    closeModals,
    executeCreativeAction,
    isGenerating,
    fps,
    setFps,
    numFrames,
    setNumFrames,
    motionBucketId,
    setMotionBucketId,
    engineId,
    setEngineId,
  } = useCreativeStore();

  const [prompt, setPrompt] = useState<string>(
    'Smooth camera pan, vivid natural motion, cinematic lighting'
  );

  if (!videoModalOpen || !referenceImage) return null;

  const currentW = referenceImage.width || 512;
  const currentH = referenceImage.height || 512;

  const handleGenerateVideo = async () => {
    if (!referenceImage?.assetId || isGenerating) return;

    const res = await executeCreativeAction({
      action: 'img2video',
      prompt,
      input_image_id: referenceImage.assetId,
      fps,
      num_frames: numFrames,
      motion_bucket_id: motionBucketId,
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
            <Clapperboard className="w-5 h-5 text-purple-400" />
            <h2 className="font-semibold text-sm text-slate-100">Animate Image (Image-to-Video)</h2>
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
          {/* Source Thumbnail Preview */}
          <div className="flex items-center gap-4 bg-slate-950 p-3 rounded-xl border border-slate-800">
            <img
              src={referenceImage.imageUrl}
              alt="Source"
              className="w-16 h-16 rounded-lg object-cover border border-slate-700"
            />
            <div className="flex flex-col text-xs">
              <span className="font-medium text-slate-200 line-clamp-1">{referenceImage.label || 'Source Asset'}</span>
              <span className="text-slate-400 mt-1">Resolution: {currentW} × {currentH} px</span>
              <span className="text-purple-400 font-medium">Output: {numFrames} frames @ {fps} fps</span>
            </div>
          </div>

          {/* Prompt */}
          <div className="flex flex-col gap-1.5 text-xs">
            <label className="text-slate-300 font-medium">Motion Prompt / Style Guide:</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={2}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-purple-500 transition resize-none"
              placeholder="Describe camera movement and animation style..."
            />
          </div>

          {/* Framerate Selection */}
          <div className="flex flex-col gap-1.5 text-xs">
            <span className="text-slate-300 font-medium">Frame Rate (FPS):</span>
            <div className="grid grid-cols-3 gap-2">
              {[8, 16, 24].map((rate) => (
                <button
                  key={rate}
                  type="button"
                  onClick={() => setFps(rate)}
                  className={`py-2 px-3 rounded-xl border font-medium transition ${
                    fps === rate
                      ? 'bg-purple-600/20 border-purple-500 text-purple-300'
                      : 'bg-slate-800/80 border-slate-700 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {rate} FPS
                </button>
              ))}
            </div>
          </div>

          {/* Frame Count Selection */}
          <div className="flex flex-col gap-1.5 text-xs">
            <span className="text-slate-300 font-medium">Video Length (Frames):</span>
            <div className="grid grid-cols-2 gap-2">
              {[16, 25].map((frames) => (
                <button
                  key={frames}
                  type="button"
                  onClick={() => setNumFrames(frames)}
                  className={`py-2 px-3 rounded-xl border font-medium transition ${
                    numFrames === frames
                      ? 'bg-purple-600/20 border-purple-500 text-purple-300'
                      : 'bg-slate-800/80 border-slate-700 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {frames} Frames (~{(frames / fps).toFixed(1)}s)
                </button>
              ))}
            </div>
          </div>

          {/* Motion Intensity Slider */}
          <div className="flex flex-col gap-1.5 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-300 font-medium">Motion Intensity (Bucket ID):</span>
              <span className="text-purple-400 font-mono">{motionBucketId}</span>
            </div>
            <input
              type="range"
              min={1}
              max={255}
              value={motionBucketId}
              onChange={(e) => setMotionBucketId(Number(e.target.value))}
              className="w-full accent-purple-500 bg-slate-950 rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-500">
              <span>Subtle (10)</span>
              <span>Balanced (127)</span>
              <span>Dynamic (200+)</span>
            </div>
          </div>

          {/* Engine Selection */}
          <div className="flex flex-col gap-1.5 text-xs">
            <label className="text-slate-300 font-medium">Execution Engine:</label>
            <select
              value={engineId}
              onChange={(e) => setEngineId(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-purple-500"
            >
              <option value="managed_comfyui">Local ComfyUI (Stable Video Diffusion / AnimateDiff)</option>
              <option value="cloud_fal">Cloud Fal.ai (Fast SVD / Luma Dream Machine)</option>
              <option value="cloud_siliconflow">Cloud SiliconFlow (CogVideoX)</option>
            </select>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="px-5 py-4 border-t border-slate-800 flex items-center justify-end gap-3 bg-slate-900/50">
          <button
            type="button"
            onClick={closeModals}
            className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleGenerateVideo}
            disabled={isGenerating}
            className="flex items-center gap-2 px-5 py-2 text-xs font-semibold rounded-xl bg-purple-600 hover:bg-purple-500 text-white shadow-lg shadow-purple-600/30 transition disabled:opacity-50"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Generating Video...</span>
              </>
            ) : (
              <>
                <Video className="w-4 h-4" />
                <span>Animate to Video</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
