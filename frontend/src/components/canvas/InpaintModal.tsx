import { useEffect, useRef, useState } from 'react';
import {
  Eraser,
  FlipHorizontal,
  Loader2,
  Paintbrush,
  RotateCcw,
  Sparkles,
  X,
} from 'lucide-react';
import { useCreativeStore } from '../../stores/useCreativeStore';

export const InpaintModal = () => {
  const { inpaintModalOpen, referenceImage, closeModals, executeCreativeAction, isGenerating } =
    useCreativeStore();
  const [inpaintPrompt, setInpaintPrompt] = useState('');
  const [brushSize, setBrushSize] = useState(32);
  const [tool, setTool] = useState<'brush' | 'eraser'>('brush');
  const [isDrawing, setIsDrawing] = useState(false);
  const [cursorPos, setCursorPos] = useState<{ x: number; y: number } | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (inpaintModalOpen && referenceImage) {
      setInpaintPrompt(referenceImage.provenance?.prompt || '');
      setTool('brush');

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
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();

    // Update screen cursor preview
    setCursorPos({ x: e.clientX, y: e.clientY });

    if (!isDrawing && e.type !== 'mousedown') return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;

    if (tool === 'eraser') {
      ctx.globalCompositeOperation = 'destination-out';
      ctx.beginPath();
      ctx.arc(x, y, brushSize * (scaleX || 1), 0, Math.PI * 2);
      ctx.fill();
    } else {
      ctx.globalCompositeOperation = 'source-over';
      ctx.fillStyle = 'rgba(255, 255, 255, 1.0)';
      ctx.beginPath();
      ctx.arc(x, y, brushSize * (scaleX || 1), 0, Math.PI * 2);
      ctx.fill();
    }
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

  const handleInvert = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = imgData.data;
    for (let i = 0; i < data.length; i += 4) {
      const alpha = data[i + 3];
      if (alpha > 0) {
        data[i + 3] = 0;
      } else {
        data[i] = 255;
        data[i + 1] = 255;
        data[i + 2] = 255;
        data[i + 3] = 255;
      }
    }
    ctx.putImageData(imgData, 0, 0);
  };

  const handleSubmit = async () => {
    const canvas = canvasRef.current;
    if (!canvas || !referenceImage?.assetId || isGenerating) return;

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-md p-4 animate-in fade-in duration-150">
      <div
        ref={containerRef}
        className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl shadow-slate-950/90 overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
              <Paintbrush className="w-4 h-4" />
            </div>
            <div>
              <h2 className="font-semibold text-sm text-slate-100">In-Place Canvas Mask Studio</h2>
              <p className="text-[11px] text-slate-400">Paint the regions you want the AI to reconstruct</p>
            </div>
          </div>
          <button
            onClick={closeModals}
            className="p-1.5 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Canvas Workspace */}
        <div className="flex-1 overflow-auto p-4 flex items-center justify-center bg-slate-950/70 relative min-h-[380px]">
          <div className="relative inline-block max-w-full max-h-[55vh] select-none rounded-xl overflow-hidden shadow-2xl border border-slate-800">
            {/* Background source image */}
            <img
              src={referenceImage.imageUrl}
              alt="Source"
              className="max-w-full max-h-[55vh] object-contain select-none pointer-events-none"
            />
            {/* Mask Drawing Canvas overlay */}
            <canvas
              ref={canvasRef}
              onMouseDown={startDrawing}
              onMouseUp={stopDrawing}
              onMouseMove={draw}
              onMouseEnter={() => setCursorPos(null)}
              onMouseLeave={() => {
                stopDrawing();
                setCursorPos(null);
              }}
              className="absolute inset-0 w-full h-full cursor-none opacity-80"
              style={{ mixBlendMode: 'screen' }}
            />
          </div>

          {/* Floating Brush Cursor Indicator */}
          {cursorPos && (
            <div
              className={`fixed pointer-events-none rounded-full border transform -translate-x-1/2 -translate-y-1/2 z-50 ${
                tool === 'eraser'
                  ? 'border-rose-400 bg-rose-500/20'
                  : 'border-amber-300 bg-amber-400/20'
              }`}
              style={{
                left: cursorPos.x,
                top: cursorPos.y,
                width: brushSize * 2,
                height: brushSize * 2,
              }}
            />
          )}
        </div>

        {/* Drawing & Mask Editing Toolbar (Issue #35) */}
        <div className="p-4 bg-slate-900 border-t border-slate-800 flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between text-xs gap-3">
            {/* Tool Selection: Brush vs Eraser */}
            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
              <button
                type="button"
                onClick={() => setTool('brush')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
                  tool === 'brush'
                    ? 'bg-amber-500 text-slate-950 shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Paintbrush className="w-3.5 h-3.5" />
                <span>Brush</span>
              </button>
              <button
                type="button"
                onClick={() => setTool('eraser')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
                  tool === 'eraser'
                    ? 'bg-rose-500 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Eraser className="w-3.5 h-3.5" />
                <span>Eraser</span>
              </button>
            </div>

            {/* Brush Size Slider */}
            <div className="flex items-center gap-2 text-slate-300 bg-slate-950 px-3 py-1.5 rounded-xl border border-slate-800">
              <span className="text-[11px] text-slate-400">Size:</span>
              <input
                type="range"
                min="6"
                max="80"
                value={brushSize}
                onChange={(e) => setBrushSize(Number(e.target.value))}
                className="w-28 accent-amber-500 cursor-pointer"
              />
              <span className="font-mono text-xs text-amber-300 w-8">{brushSize}px</span>
            </div>

            {/* Mask Actions: Invert & Clear */}
            <div className="flex items-center gap-1.5">
              <button
                onClick={handleInvert}
                title="Invert Mask Selection"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition"
              >
                <FlipHorizontal className="w-3.5 h-3.5" />
                <span>Invert</span>
              </button>
              <button
                onClick={handleClear}
                title="Clear All Mask Strokes"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Clear</span>
              </button>
            </div>
          </div>

          {/* Prompt and Inpaint Submission */}
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={inpaintPrompt}
              onChange={(e) => setInpaintPrompt(e.target.value)}
              placeholder="Describe what should be synthesized in the masked area..."
              className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500 transition"
              disabled={isGenerating}
            />
            <button
              onClick={handleSubmit}
              disabled={isGenerating || !inpaintPrompt.trim()}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white text-sm font-medium shadow-lg shadow-amber-600/20 transition whitespace-nowrap"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Inpainting...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Synthesize</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
