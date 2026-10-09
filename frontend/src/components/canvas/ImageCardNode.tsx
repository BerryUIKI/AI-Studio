import { memo, useEffect, useRef, useState } from 'react';
import { NodeProps } from '@xyflow/react';
import {
  Download,
  Maximize2,
  Paintbrush,
  Sparkles,
  Trash2,
  Video,
  GitBranch,
  Loader2,
  AlertTriangle,
  RefreshCw,
  Upload,
} from 'lucide-react';
import { ImageCardData } from '../../types/creative';
import { useCreativeStore } from '../../stores/useCreativeStore';
import { useCanvasStore } from '../../stores/useCanvasStore';
import { creativeRequestFromProvenance } from '../../utils/creativeReplay';
import { downloadOriginalMedia, mediaCardFields } from '../../utils/media';
import { CardMedia } from './CardMedia';
import { FloatingCardToolbar } from './FloatingCardToolbar';

export const ImageCardNode = memo(({ id, data, selected }: NodeProps) => {
  const cardData = data as unknown as ImageCardData;
  const { setReferenceImage, openInpaint, openUpscale, openImg2Video, executeCreativeAction } = useCreativeStore();
  const { removeNode, arrangeBranchTree } = useCanvasStore();

  const [isMissingAsset, setIsMissingAsset] = useState<boolean>(Boolean(cardData.isMissing));
  const [retryNonce, setRetryNonce] = useState<number>(0);
  const [isReuploading, setIsReuploading] = useState<boolean>(false);
  const replaceFileInputRef = useRef<HTMLInputElement>(null);

  const isGenerating = Boolean(cardData.isGenerating);
  const isVideo = cardData.mediaType === 'video' || Boolean(cardData.videoUrl);
  const targetMediaUrl = cardData.videoUrl || cardData.imageUrl || '';
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    if (!cardData.assetId || cardData.mimeType) return;
    const controller = new AbortController();
    void fetch(`/api/v1/assets/${encodeURIComponent(cardData.assetId)}`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) return;
        const asset = await response.json();
        if (controller.signal.aborted || !asset.mime_type) return;
        useCanvasStore.setState((state) => ({ nodes: state.nodes.map((node) =>
          node.id === id ? { ...node, data: { ...node.data, ...mediaCardFields(asset) } } : node) }));
        setIsMissingAsset(false);
        useCanvasStore.getState().notifyCanvasChange();
      }).catch(() => { /* Preview retains its existing missing-file recovery. */ });
    return () => controller.abort();
  }, [id, cardData.assetId, cardData.mimeType]);

  const handleReplaceFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsReuploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const resp = await fetch('/api/v1/creative/upload', {
        method: 'POST',
        body: formData,
      });
      if (resp.ok) {
        const asset = await resp.json();
        useCanvasStore.getState().updateNodeData(id, {
          ...mediaCardFields(asset),
          assetId: asset.id,
          imageUrl: `/api/v1/assets/${asset.id}/content`,
          videoUrl: asset.mime_type?.startsWith('video/') ? `/api/v1/assets/${asset.id}/content` : undefined,
          mediaType: asset.mime_type?.startsWith('video/') ? 'video' : 'image',
          width: asset.width || cardData.width,
          height: asset.height || cardData.height,
          label: asset.filename,
          isMissing: false,
        });
        setIsMissingAsset(false);
      }
    } catch (err) {
      console.error('Failed to replace file:', err);
    } finally {
      setIsReuploading(false);
      e.target.value = '';
    }
  };

  const handleRegenerate = async () => {
    if (!cardData.provenance) return;
    setIsMissingAsset(false);
    await executeCreativeAction(creativeRequestFromProvenance(cardData.provenance));
  };

  const handleExport = (e: React.MouseEvent) => {
    e.stopPropagation();
    setExportError(null);
    void downloadOriginalMedia(cardData).catch((error: unknown) =>
      setExportError(error instanceof Error ? error.message : 'Could not export media'));
  };

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    removeNode(id);
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
  const hasLineage = Boolean(p?.source_asset_id);

  return (
    <div
      className={`group relative rounded-2xl bg-slate-900 border transition-all duration-200 overflow-visible shadow-2xl ${
        selected
          ? 'border-indigo-500 ring-2 ring-indigo-500/30'
          : isMissingAsset
          ? 'border-rose-500/60 ring-1 ring-rose-500/30 hover:border-rose-400'
          : 'border-slate-800 hover:border-slate-700'
      }`}
      style={{ width: 320 }}
    >
      {/* Floating In-Place Action Bar for Selected Card (Issue #34) */}
      {selected && !isGenerating && (
        <FloatingCardToolbar nodeId={id} data={cardData} />
      )}

      {/* Card Content Container (with overflow-hidden for border-radius clipping) */}
      <div className="rounded-2xl overflow-hidden bg-slate-900">
        {/* Hover Action Bar (Top Right) */}
        {!isGenerating && (
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
        )}

        {/* Media Preview Container / Generating Stage Container */}
        <div className="relative bg-slate-950 flex items-center justify-center min-h-[220px] max-h-[360px] overflow-hidden">
          {isGenerating ? (
            /* Observed state with an indeterminate activity indicator. */
            <div className="w-full h-64 p-6 flex flex-col items-center justify-center relative bg-gradient-to-b from-slate-950 via-indigo-950/20 to-slate-950">
              {/* Activity decoration does not represent a provider preview. */}
              <div
                className="absolute inset-0 opacity-20 bg-[radial-gradient(#6366f1_1px,transparent_1px)] [background-size:16px_16px] animate-pulse"
              />

              <div className="relative z-10 flex flex-col items-center gap-3 w-full max-w-[240px] text-center">
                <div className="relative">
                  <div className="w-12 h-12 rounded-2xl bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400 shadow-xl shadow-indigo-600/20">
                    <Loader2 className="w-6 h-6 animate-spin" />
                  </div>
                  <span className="absolute -top-1 -right-1 flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-indigo-500"></span>
                  </span>
                </div>

                <div className="space-y-1 w-full">
                  <span className="text-xs font-semibold text-slate-200 block">
                    {cardData.generationStage || 'Generating...'}
                  </span>
                  <p className="text-[10px] text-slate-400">Waiting for an execution outcome</p>
                </div>
              </div>
            </div>
          ) : isMissingAsset ? (
            /* Actionable Missing File Recovery State */
            <div
              data-testid="missing-asset-recovery"
              className="w-full min-h-[220px] p-5 flex flex-col items-center justify-center text-center bg-rose-950/20 border border-rose-500/30 rounded-xl m-2"
            >
              <div className="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-rose-400 mb-2">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <span className="text-xs font-semibold text-rose-200">Asset File Missing</span>
              <p className="text-[11px] text-slate-400 mt-1 line-clamp-2 max-w-[240px]">
                {cardData.label || 'Referenced file cannot be found on disk.'}
              </p>
              {cardData.assetId && (
                <span className="text-[10px] text-slate-500 font-mono mt-0.5 truncate max-w-[220px]">
                  ID: {cardData.assetId}
                </span>
              )}

              <div className="mt-3 flex flex-col gap-1.5 w-full max-w-[220px]">
                <input
                  type="file"
                  ref={replaceFileInputRef}
                  onChange={handleReplaceFile}
                  accept="image/*,video/*"
                  className="hidden"
                  data-testid="replace-file-input"
                />
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    replaceFileInputRef.current?.click();
                  }}
                  disabled={isReuploading}
                  className="w-full py-1.5 px-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium flex items-center justify-center gap-1.5 transition shadow"
                >
                  {isReuploading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Uploading...</span>
                    </>
                  ) : (
                    <>
                      <Upload className="w-3.5 h-3.5" />
                      <span>Locate / Replace File</span>
                    </>
                  )}
                </button>

                <div className="flex gap-1.5 w-full">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setRetryNonce((n) => n + 1);
                      setIsMissingAsset(false);
                    }}
                    className="flex-1 py-1 px-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium flex items-center justify-center gap-1 transition border border-slate-700"
                  >
                    <RefreshCw className="w-3 h-3" />
                    <span>Retry</span>
                  </button>

                  {p && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRegenerate();
                      }}
                      className="flex-1 py-1 px-2 bg-indigo-950 hover:bg-indigo-900 text-indigo-300 rounded-lg text-xs font-medium flex items-center justify-center gap-1 transition border border-indigo-800"
                    >
                      <Sparkles className="w-3 h-3" />
                      <span>Regenerate</span>
                    </button>
                  )}

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeNode(id);
                    }}
                    className="py-1 px-2 bg-rose-950/60 hover:bg-rose-900/60 text-rose-300 rounded-lg text-xs font-medium flex items-center justify-center transition border border-rose-800/60"
                    title="Remove missing card"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>
            </div>
          ) : (
            /* Media Render (Image or Video) */
            <>
              <CardMedia data={cardData} url={retryNonce ? `${targetMediaUrl}?t=${retryNonce}` : targetMediaUrl}
                onError={() => setIsMissingAsset(true)} />
              {cardData.isAnimated && (
                <div className="absolute top-2 left-2 px-2 py-0.5 rounded-md bg-purple-950/80 text-[10px] text-purple-300">
                  Animated image
                </div>
              )}
              {exportError && <p role="alert" className="absolute bottom-2 right-2 text-xs text-red-300">{exportError}</p>}

              {p && (
                <div className="absolute bottom-2 left-2 px-2 py-0.5 rounded-md bg-slate-950/75 backdrop-blur text-[10px] font-mono text-slate-300 border border-slate-800">
                  {p.dimensions}
                  {p.fps ? ` · ${p.fps}fps` : ''}
                  {p.duration_seconds ? ` · ${p.duration_seconds}s` : ''}
                </div>
              )}
            </>
          )}
        </div>

        {/* Provenance & Metadata Details Footer */}
        <div className="p-3 bg-slate-900 border-t border-slate-800/80">
          <div className="flex items-start justify-between gap-2">
            <p className="text-xs text-slate-200 font-medium line-clamp-2 leading-relaxed flex-1">
              {cardData.label || 'Untitled Asset'}
            </p>
            {hasLineage && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  arrangeBranchTree(id);
                }}
                title="Lineage variation (Click to align branch tree)"
                className="p-1 rounded-md bg-indigo-950/60 text-indigo-400 hover:text-indigo-200 border border-indigo-800/50 hover:bg-indigo-900/60 transition"
              >
                <GitBranch className="w-3 h-3" />
              </button>
            )}
          </div>

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
            <div className="mt-2 text-[10px] text-slate-500">
              {isGenerating ? 'Synthesizing...' : 'Imported asset'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

ImageCardNode.displayName = 'ImageCardNode';
