import { memo } from 'react';
import { NodeProps } from '@xyflow/react';
import { Download, Maximize2, Paintbrush, Sparkles, Trash2, Video } from 'lucide-react';
import { ImageCardData } from '../../types/creative';
import { useCreativeStore } from '../../stores/useCreativeStore';
import { useCanvasStore } from '../../stores/useCanvasStore';

export const ImageCardNode = memo(({ id, data, selected }: NodeProps) => {
  const cardData = data as unknown as ImageCardData;
  const { setReferenceImage, openInpaint, openUpscale, openImg2Video } = useCreativeStore();
  const { nodes } = useCanvasStore();

  const isVideo = cardData.mediaType === 'video' || Boolean(cardData.videoUrl);

  const handleExport = (e: React.MouseEvent) => {
    e.stopPropagation();
    const link = document.createElement('a');
    link.href = cardData.videoUrl || cardData.imageUrl;
    const ext = isVideo ? 'mp4' : 'png';
    link.download = `${cardData.label || 'berry_asset'}.${ext}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    useCanvasStore.setState({
      nodes: nodes.filter((n) => n.id !== id),
    });
  };

  const handleVary = (e: React.MouseEvent) => {
    e.stopPropagation();
    setReferenceImage(cardData);
  };

  const handleInpaint = (e: React.MouseEvent) => {
    e.stopPropagation();
    openInpaint(cardData);
  };

  const handleUpscale = (e: React.MouseEvent) => {
    e.stopPropagation();
    openUpscale(cardData);
  };

  const handleAnimate = (e: React.MouseEvent) => {
    e.stopPropagation();
    openImg2Video(cardData);
  };

  const p = cardData.provenance;

  return (
    <div
      className={`group relative rounded-2xl bg-slate-900 border transition-all duration-200 overflow-hidden shadow-2xl ${
        selected ? 'border-indigo-500 ring-2 ring-indigo-500/30' : 'border-slate-800 hover:border-slate-700'
      }`}
      style={{ width: 320 }}
    >
      {/* Floating Action Bar */}
      <div className="absolute top-2.5 right-2.5 z-10 flex items-center gap-1 bg-slate-950/85 backdrop-blur-md rounded-xl p-1 border border-slate-700/60 opacity-0 group-hover:opacity-100 transition-opacity shadow-lg">
        {!isVideo && (
          <>
            <button
              onClick={handleAnimate}
              title="Animate (Image-to-Video)"
              className="p-1.5 rounded-lg text-slate-300 hover:text-purple-400 hover:bg-slate-800 transition"
            >
              <Video className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleVary}
              title="Vary (Image-to-Image)"
              className="p-1.5 rounded-lg text-slate-300 hover:text-indigo-400 hover:bg-slate-800 transition"
            >
              <Sparkles className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleInpaint}
              title="Inpaint / Mask"
              className="p-1.5 rounded-lg text-slate-300 hover:text-amber-400 hover:bg-slate-800 transition"
            >
              <Paintbrush className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleUpscale}
              title="Upscale Image"
              className="p-1.5 rounded-lg text-slate-300 hover:text-emerald-400 hover:bg-slate-800 transition"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
          </>
        )}
        <button
          onClick={handleExport}
          title="Export / Download"
          className="p-1.5 rounded-lg text-slate-300 hover:text-blue-400 hover:bg-slate-800 transition"
        >
          <Download className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={handleRemove}
          title="Remove from Canvas"
          className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Media Preview Container */}
      <div className="relative bg-slate-950 flex items-center justify-center min-h-[220px] max-h-[360px] overflow-hidden">
        {isVideo ? (
          <video
            src={cardData.videoUrl || cardData.imageUrl}
            controls
            loop
            playsInline
            className="w-full h-auto object-contain max-h-[360px]"
          />
        ) : (
          <img
            src={cardData.imageUrl}
            alt={cardData.label || 'Generated creative asset'}
            className="w-full h-auto object-contain select-none pointer-events-none"
            loading="lazy"
          />
        )}
        {p && (
          <div className="absolute bottom-2 left-2 px-2 py-0.5 rounded-md bg-slate-950/75 backdrop-blur text-[10px] font-mono text-slate-300 border border-slate-800">
            {p.dimensions}
            {p.fps ? ` · ${p.fps}fps` : ''}
            {p.duration_seconds ? ` · ${p.duration_seconds}s` : ''}
          </div>
        )}
      </div>

      {/* Provenance & Metadata Details Footer */}
      <div className="p-3 bg-slate-900 border-t border-slate-800/80">
        <p className="text-xs text-slate-200 font-medium line-clamp-2 leading-relaxed">
          {cardData.label || 'Untitled Asset'}
        </p>

        {p ? (
          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[10px] text-slate-400">
            <span className="px-1.5 py-0.5 rounded bg-indigo-950/60 text-indigo-300 border border-indigo-800/40">
              {p.engine_id.replace('managed_', '')}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
              {p.action}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
              seed: {p.seed}
            </span>
            {p.fps && (
              <span className="px-1.5 py-0.5 rounded bg-purple-950/60 text-purple-300 border border-purple-800/40">
                {p.fps} fps
              </span>
            )}
          </div>
        ) : (
          <div className="mt-2 text-[10px] text-slate-500">Imported asset</div>
        )}
      </div>
    </div>
  );
});

ImageCardNode.displayName = 'ImageCardNode';

