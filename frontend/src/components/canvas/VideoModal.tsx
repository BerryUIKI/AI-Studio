import { formatNumber } from '../../i18n/format';
import { useUiText } from '../../i18n/useUiText';
import { Dialog } from '../ui/Dialog';
import { useState } from 'react';
import { Clapperboard, Loader2, Video, X } from 'lucide-react';
import { useCreativeStore } from '../../stores/useCreativeStore';

export const VideoModal = () => {
  const ui = useUiText();
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
    <Dialog title={ui("ui_experimental_video_creation")} onClose={closeModals} className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Clapperboard className="w-5 h-5 text-purple-400" />
            <h2 className="font-semibold text-sm text-slate-100">{ui("ui_animate_image_image_to_video")}</h2>
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
          {/* Source Thumbnail Preview */}
          <div className="flex items-center gap-4 bg-slate-950 p-3 rounded-xl border border-slate-800">
            <img
              src={referenceImage.imageUrl}
              alt={ui("ui_source")}
              className="w-16 h-16 rounded-lg object-cover border border-slate-700"
            />
            <div className="flex flex-col text-xs">
              <span className="font-medium text-slate-200 line-clamp-1">{referenceImage.label || ui("ui_source_asset")}</span>
              <span className="text-slate-400 mt-1">{ui("ui_resolution")}{currentW} × {currentH} {ui("ui_px")}</span>
              <span className="text-purple-400 font-medium">{ui("ui_output")}{numFrames} {ui("ui_frames")}{fps} {ui("ui_fps")}</span>
            </div>
          </div>

          {/* Prompt */}
          <div className="flex flex-col gap-1.5 text-xs">
            <label className="text-slate-300 font-medium">{ui("ui_motion_prompt_style_guide")}</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={2}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-purple-500 transition resize-none"
              placeholder={ui("ui_describe_camera_movement_and_animation_style")}
            />
          </div>

          {/* Framerate Selection */}
          <div className="flex flex-col gap-1.5 text-xs">
            <span className="text-slate-300 font-medium">{ui("ui_frame_rate_fps")}</span>
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
                  {rate} {ui("ui_fps_2")}</button>
              ))}
            </div>
          </div>

          {/* Frame Count Selection */}
          <div className="flex flex-col gap-1.5 text-xs">
            <span className="text-slate-300 font-medium">{ui("ui_video_length_frames")}</span>
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
                  {frames} {ui("ui_frames_2")}{formatNumber((frames / fps), 1, 1)}{ui("ui_s_2")}</button>
              ))}
            </div>
          </div>

          {/* Motion Intensity Slider */}
          <div className="flex flex-col gap-1.5 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-300 font-medium">{ui("ui_motion_intensity_bucket_id")}</span>
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
              <span>{ui("ui_subtle_10")}</span>
              <span>{ui("ui_balanced_127")}</span>
              <span>{ui("ui_dynamic_200")}</span>
            </div>
          </div>

          {/* Engine Selection */}
          <div className="flex flex-col gap-1.5 text-xs">
            <label className="text-slate-300 font-medium">{ui("ui_execution_engine")}</label>
            <select
              value={engineId}
              onChange={(e) => setEngineId(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-purple-500"
            >
              <option value="managed_comfyui">{ui("ui_local_comfyui_stable_video_diffusion_animatediff")}</option>
              <option value="cloud_fal">{ui("ui_cloud_fal_ai_fast_svd_luma_dream_machine")}</option>
              <option value="cloud_siliconflow">{ui("ui_cloud_siliconflow_cogvideox")}</option>
            </select>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="px-5 py-4 border-t border-slate-800 flex items-center justify-end gap-3 bg-slate-900/50">
          <button
            type="button"
            onClick={closeModals}
            aria-label={ui("ui_close_dialog")}
            className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition"
          >
            {ui("ui_cancel")}</button>
          <button
            type="button"
            onClick={handleGenerateVideo}
            disabled={isGenerating}
            className="flex items-center gap-2 px-5 py-2 text-xs font-semibold rounded-xl bg-purple-600 hover:bg-purple-500 text-white shadow-lg shadow-purple-600/30 transition disabled:opacity-50"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>{ui("ui_generating_video")}</span>
              </>
            ) : (
              <>
                <Video className="w-4 h-4" />
                <span>{ui("ui_animate_to_video")}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </Dialog>
  );
};
