import {
  Download,
  GitBranch,
  Maximize2,
  Paintbrush,
  Sparkles,
  Trash2,
  Video,
  Copy,
} from 'lucide-react';
import { ImageCardData } from '../../types/creative';
import { useCreativeStore } from '../../stores/useCreativeStore';
import { useCanvasStore } from '../../stores/useCanvasStore';

interface FloatingCardToolbarProps {
  nodeId: string;
  data: ImageCardData;
}

export const FloatingCardToolbar: React.FC<FloatingCardToolbarProps> = ({ nodeId, data }) => {
  const { setReferenceImage, openInpaint, openUpscale, openImg2Video } = useCreativeStore();
  const { duplicateNode, removeNode, arrangeBranchTree } = useCanvasStore();

  const isVideo = data.mediaType === 'video' || Boolean(data.videoUrl);
  const targetMediaUrl = data.videoUrl || data.imageUrl || '';

  const handleExport = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!targetMediaUrl) return;
    const link = document.createElement('a');
    link.href = targetMediaUrl;
    link.download = `${data.label || 'berry_asset'}.${isVideo ? 'mp4' : 'png'}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleDuplicate = (e: React.MouseEvent) => {
    e.stopPropagation();
    duplicateNode(nodeId);
  };

  const handleArrangeTree = (e: React.MouseEvent) => {
    e.stopPropagation();
    arrangeBranchTree(nodeId);
  };

  return (
    <div
      className="absolute -bottom-14 left-1/2 -translate-x-1/2 z-30 flex items-center gap-1 bg-slate-900/95 backdrop-blur-xl border border-indigo-500/40 rounded-2xl p-1.5 shadow-2xl shadow-slate-950/80 animate-in fade-in zoom-in-95 duration-150 pointer-events-auto"
      onClick={(e) => e.stopPropagation()}
    >
      {!isVideo && (
        <>
          <button
            onClick={() => setReferenceImage(data)}
            title="Vary (Image-to-Image reference)"
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-medium text-indigo-300 hover:text-white hover:bg-indigo-600/30 transition"
          >
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span>Vary</span>
          </button>

          <button
            onClick={() => openInpaint(data)}
            title="Inpaint / Mask"
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-medium text-amber-300 hover:text-white hover:bg-amber-600/30 transition"
          >
            <Paintbrush className="w-3.5 h-3.5 text-amber-400" />
            <span>Inpaint</span>
          </button>

          <button
            onClick={() => openUpscale(data)}
            title="Upscale Resolution"
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-medium text-emerald-300 hover:text-white hover:bg-emerald-600/30 transition"
          >
            <Maximize2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>Upscale</span>
          </button>

          <button
            onClick={() => openImg2Video(data)}
            title="Animate to Video"
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-medium text-purple-300 hover:text-white hover:bg-purple-600/30 transition"
          >
            <Video className="w-3.5 h-3.5 text-purple-400" />
            <span>Animate</span>
          </button>

          <div className="w-[1px] h-4 bg-slate-800 mx-0.5" />
        </>
      )}

      {/* Tree / Lineage branch alignment */}
      <button
        onClick={handleArrangeTree}
        title="Arrange Branch Tree (Auto-align lineage hierarchy)"
        className="p-1.5 rounded-xl text-slate-300 hover:text-indigo-400 hover:bg-slate-800 transition"
      >
        <GitBranch className="w-3.5 h-3.5" />
      </button>

      {/* Duplicate */}
      <button
        onClick={handleDuplicate}
        title="Duplicate Card (Ctrl+D)"
        className="p-1.5 rounded-xl text-slate-300 hover:text-slate-100 hover:bg-slate-800 transition"
      >
        <Copy className="w-3.5 h-3.5" />
      </button>

      {/* Download */}
      <button
        onClick={handleExport}
        title="Export Asset"
        className="p-1.5 rounded-xl text-slate-300 hover:text-slate-100 hover:bg-slate-800 transition"
      >
        <Download className="w-3.5 h-3.5" />
      </button>

      {/* Delete */}
      <button
        onClick={() => removeNode(nodeId)}
        title="Delete (Backspace / Del)"
        className="p-1.5 rounded-xl text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};
