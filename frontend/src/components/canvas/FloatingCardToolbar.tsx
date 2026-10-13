import { useUiText } from '../../i18n/useUiText';
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
import { creativeRequestFromProvenance } from '../../utils/creativeReplay';
import { downloadOriginalMedia } from '../../utils/media';

interface FloatingCardToolbarProps {
  nodeId: string;
  data: ImageCardData;
}

export const FloatingCardToolbar: React.FC<FloatingCardToolbarProps> = ({ nodeId, data }) => {
  const ui = useUiText();
  const { setReferenceImage, openInpaint, openUpscale, openImg2Video } = useCreativeStore();
  const { duplicateNode, removeNode, arrangeBranchTree } = useCanvasStore();
  const isGenerating = useCreativeStore((state) => state.isGenerating);
  const executeCreativeAction = useCreativeStore((state) => state.executeCreativeAction);

  const isVideo = data.mediaType === 'video' || Boolean(data.videoUrl);

  const handleExport = (e: React.MouseEvent) => {
    e.stopPropagation();
    void downloadOriginalMedia(data).catch((error: unknown) => useCreativeStore.setState({
      error: error instanceof Error ? error.message : 'Could not export media',
    }));
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
      role="group"
      aria-label={ui("ui_selected_asset")}
      className="flex flex-wrap items-center gap-1 bg-slate-900/95 border border-indigo-500/40 rounded-xl p-1.5 pointer-events-auto"
      onClick={(e) => e.stopPropagation()}
    >
      {!isVideo && (
        <>
          <button
            onClick={() => setReferenceImage(data)}
            title={ui("ui_vary_image_to_image_reference")}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-medium text-indigo-300 hover:text-white hover:bg-indigo-600/30 transition"
          >
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span>{ui("ui_vary")}</span>
          </button>

          <button
            onClick={() => openInpaint(data)}
            title={ui("ui_inpaint_mask")}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-medium text-amber-300 hover:text-white hover:bg-amber-600/30 transition"
          >
            <Paintbrush className="w-3.5 h-3.5 text-amber-400" />
            <span>{ui("ui_inpaint")}</span>
          </button>

          <button
            onClick={() => openUpscale(data)}
            title={ui("ui_upscale_resolution")}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-medium text-emerald-300 hover:text-white hover:bg-emerald-600/30 transition"
          >
            <Maximize2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>{ui("ui_upscale")}</span>
          </button>

          <button
            onClick={() => openImg2Video(data)}
            title={ui("ui_animate_to_video")}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-medium text-purple-300 hover:text-white hover:bg-purple-600/30 transition"
          >
            <Video className="w-3.5 h-3.5 text-purple-400" />
            <span>{ui("ui_animate")}</span>
          </button>

          <div className="w-[1px] h-4 bg-slate-800 mx-0.5" />
        </>
      )}

      {/* Tree / Lineage branch alignment */}
      <button
        onClick={handleArrangeTree}
        title={ui("ui_arrange_branch_tree_auto_align_lineage_hierarchy")}
        className="p-1.5 rounded-xl text-slate-300 hover:text-indigo-400 hover:bg-slate-800 transition"
      >
        <GitBranch className="w-3.5 h-3.5" />
      </button>

      {/* Duplicate */}
      <button
        onClick={handleDuplicate}
        title={ui("ui_reuse_this_result_without_generation_ctrl_d")}
        className="p-1.5 rounded-xl text-slate-300 hover:text-slate-100 hover:bg-slate-800 transition"
      >
        <Copy className="w-3.5 h-3.5" />
        <span className="text-xs ml-1">{ui("ui_reuse")}</span>
      </button>

      {data.provenance && (
        <button
          disabled={isGenerating}
          onClick={() => {
            if (data.provenance) void executeCreativeAction(creativeRequestFromProvenance(data.provenance, true));
          }}
          title={ui("ui_generate_with_saved_settings_and_a_new_random")}
          className="flex items-center gap-1 p-1.5 rounded-xl text-xs text-indigo-300 hover:bg-slate-800 disabled:opacity-50"
        >
          <Sparkles className="w-3.5 h-3.5" />
          {ui("ui_new_variation")}</button>
      )}

      {/* Download */}
      <button
        onClick={handleExport}
        title={ui("ui_export_asset")}
        className="p-1.5 rounded-xl text-slate-300 hover:text-slate-100 hover:bg-slate-800 transition"
      >
        <Download className="w-3.5 h-3.5" />
      </button>

      {/* Delete */}
      <button
        onClick={() => removeNode(nodeId)}
        title={ui("ui_delete_backspace_del")}
        className="p-1.5 rounded-xl text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};
