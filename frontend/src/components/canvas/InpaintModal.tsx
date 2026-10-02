import { useEffect, useRef, useState } from 'react';
import { Loader2, Paintbrush, RotateCcw, Sparkles, X } from 'lucide-react';
import { useCreativeStore } from '../../stores/useCreativeStore';

export const InpaintModal = () => {
  const { inpaintModalOpen, referenceImage, closeModals, executeCreativeAction, isGenerating } =
    useCreativeStore();
  const [inpaintPrompt, setInpaintPrompt] = useState('');
  const [brushSize, setBrushSize] = useState(30);
  const [isDrawing, setIsDrawing] = useState(false);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);

  useEffect(() => {
    if (inpaintModalOpen && referenceImage) {
      setInpaintPrompt(referenceImage.provenance?.prompt || '');
      // Initialize mask canvas once image loads
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.src = referenceImage.imageUrl;
      img.onload = () => {
        imageRef.current = img;
        const canvas = canvasRef.current;
        if (canvas) {
          canvas.width = img.naturalWidth || 512;
          canvas.height = img.naturalHeight || 512;
          const ctx = canvas.getContext('2d');
          if (ctx) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
          }
        }
      };
    }
  }, [inpaintModalOpen, referenceImage]);

  if (!inpaintModalOpen || !referenceImage) return null;

  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDrawing(true);
    draw(e);
  };

  const stopDrawing = () => {
    setIsDrawing(false);
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing && e.type !== 'mousedown') return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;

    ctx.fillStyle = 'rgba(255, 255, 255, 1.0)';
    ctx.beginPath();
    ctx.arc(x, y, brushSize, 0, Math.PI * 2);
    ctx.fill();
  };

  const handleClear = () => {
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    }
  };

  const handleSubmit = async () => {
    const canvas = canvasRef.current;
    if (!canvas || !referenceImage?.assetId || isGenerating) return;

    // Export mask canvas as Blob
    canvas.toBlob(async (blob) => {
      if (!blob) return;
      const formData = new FormData();
      formData.append('file', blob, 'inpaint_mask.png');

      try {
        const uploadResp = await fetch('/api/v1/creative/upload', {
          method: 'POST',
          body: formData,
        });
        if (!uploadResp.ok) throw new Error('Failed to upload mask');
        const maskAsset = await uploadResp.json();

        const res = await executeCreativeAction({
          action: 'inpaint',
          prompt: inpaintPrompt,
          input_image_id: referenceImage.assetId,
          mask_image_id: maskAsset.id,
        });

        if (res && res.success) {
          closeModals();
        }
      } catch (err: any) {
        useCreativeStore.setState({ error: err.message || 'Inpainting failed' });
      }
    }, 'image/png');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Paintbrush className="w-5 h-5 text-amber-400" />
            <h2 className="font-semibold text-sm text-slate-100">Inpaint & Retouch Mask</h2>
          </div>
          <button
            onClick={closeModals}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Canvas Workspace */}
        <div className="flex-1 overflow-auto p-4 flex items-center justify-center bg-slate-950 relative min-h-[380px]">
          <div className="relative inline-block max-w-full max-h-[55vh] select-none">
            {/* Background source image */}
            <img
              src={referenceImage.imageUrl}
              alt="Source"
              className="max-w-full max-h-[55vh] object-contain rounded-lg pointer-events-none"
            />
            {/* Mask Drawing Canvas overlay */}
            <canvas
              ref={canvasRef}
              onMouseDown={startDrawing}
              onMouseUp={stopDrawing}
              onMouseMove={draw}
              onMouseLeave={stopDrawing}
              className="absolute inset-0 w-full h-full cursor-crosshair opacity-75"
              style={{ mixBlendMode: 'screen' }}
            />
          </div>
        </div>

        {/* Drawing & Prompt Toolbar */}
        <div className="p-4 bg-slate-900 border-t border-slate-800 flex flex-col gap-3">
          <div className="flex items-center justify-between text-xs gap-4">
            {/* Brush Size */}
            <div className="flex items-center gap-2 text-slate-300">
              <span>Brush Size:</span>
              <input
                type="range"
                min="5"
                max="80"
                value={brushSize}
                onChange={(e) => setBrushSize(Number(e.target.value))}
                className="w-32 accent-amber-500"
              />
              <span className="font-mono text-slate-400">{brushSize}px</span>
            </div>

            {/* Clear Mask Button */}
            <button
              onClick={handleClear}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Clear Mask</span>
            </button>
          </div>

          {/* Prompt and Submit */}
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={inpaintPrompt}
              onChange={(e) => setInpaintPrompt(e.target.value)}
              placeholder="Describe what should appear in the painted mask area..."
              className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-4 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500"
              disabled={isGenerating}
            />
            <button
              onClick={handleSubmit}
              disabled={isGenerating || !inpaintPrompt.trim()}
              className="flex items-center gap-2 px-5 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white text-sm font-medium shadow-lg transition whitespace-nowrap"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Inpainting...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Generate Inpaint</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
