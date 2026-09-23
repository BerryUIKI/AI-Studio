import { create } from 'zustand';
import { CreativeActionRequest, CreativeActionResult, ImageCardData } from '../types/creative';
import { useCanvasStore } from './useCanvasStore';

interface CreativeState {
  prompt: string;
  negativePrompt: string;
  aspectRatio: string;
  steps: number;
  cfgScale: number;
  seed: number;
  engineId: string;
  model: string;
  referenceImage: ImageCardData | null;
  inpaintModalOpen: boolean;
  upscaleModalOpen: boolean;
  isGenerating: boolean;
  error: string | null;

  setPrompt: (prompt: string) => void;
  setNegativePrompt: (np: string) => void;
  setAspectRatio: (ar: string) => void;
  setEngineId: (id: string) => void;
  setModel: (m: string) => void;
  setReferenceImage: (img: ImageCardData | null) => void;
  openInpaint: (img: ImageCardData) => void;
  openUpscale: (img: ImageCardData) => void;
  closeModals: () => void;
  randomizeSeed: () => void;
  executeCreativeAction: (override?: Partial<CreativeActionRequest>) => Promise<CreativeActionResult | null>;
  uploadCanvasImage: (file: File, position?: { x: number; y: number }) => Promise<void>;
}

export const useCreativeStore = create<CreativeState>((set, get) => ({
  prompt: 'A picturesque mountain village during golden hour, cinematic lighting, ultra-detailed',
  negativePrompt: 'low quality, blurry, deformed, bad anatomy',
  aspectRatio: '1:1',
  steps: 20,
  cfgScale: 7.0,
  seed: -1,
  engineId: 'managed_comfyui',
  model: 'v1-5-pruned-emaonly.safetensors',
  referenceImage: null,
  inpaintModalOpen: false,
  upscaleModalOpen: false,
  isGenerating: false,
  error: null,

  setPrompt: (prompt) => set({ prompt }),
  setNegativePrompt: (negativePrompt) => set({ negativePrompt }),
  setAspectRatio: (aspectRatio) => set({ aspectRatio }),
  setEngineId: (engineId) => set({ engineId }),
  setModel: (model) => set({ model }),
  setReferenceImage: (referenceImage) => set({ referenceImage }),
  openInpaint: (img) => set({ referenceImage: img, inpaintModalOpen: true }),
  openUpscale: (img) => set({ referenceImage: img, upscaleModalOpen: true }),
  closeModals: () => set({ inpaintModalOpen: false, upscaleModalOpen: false }),
  randomizeSeed: () => set({ seed: Math.floor(Math.random() * 2147483647) }),

  executeCreativeAction: async (override) => {
    const s = get();
    set({ isGenerating: true, error: null });

    const action = override?.action || (s.referenceImage ? 'img2img' : 'txt2img');
    const payload: CreativeActionRequest = {
      action,
      prompt: s.prompt,
      negative_prompt: s.negativePrompt,
      model: s.model,
      engine_id: s.engineId,
      aspect_ratio: s.aspectRatio,
      steps: s.steps,
      cfg_scale: s.cfgScale,
      seed: s.seed,
      input_image_id: s.referenceImage?.assetId,
      ...override,
    };

    try {
      const resp = await fetch('/api/v1/creative/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        throw new Error(`Server returned HTTP ${resp.status}`);
      }

      const result: CreativeActionResult = await resp.json();
      if (!result.success || !result.image_url) {
        throw new Error(result.error_message || 'Image generation failed');
      }

      // Add as ImageCard on canvas
      const canvasStore = useCanvasStore.getState();
      const existingNodes = canvasStore.nodes;
      const xOffset = 80 + (existingNodes.length % 5) * 360;
      const yOffset = 80 + Math.floor(existingNodes.length / 5) * 420;

      const newCardId = `image_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
      const cardData: ImageCardData = {
        assetId: result.asset_id,
        imageUrl: result.image_url,
        width: result.width,
        height: result.height,
        provenance: result.provenance,
        label: result.provenance?.prompt || s.prompt,
      };

      const newCardNode = {
        id: newCardId,
        type: 'imageCard',
        position: { x: xOffset, y: yOffset },
        data: cardData as any,
      };

      useCanvasStore.setState({
        nodes: [...existingNodes, newCardNode],
        selectedNodeId: newCardId,
      });

      set({ isGenerating: false });
      return result;
    } catch (err: any) {
      set({ isGenerating: false, error: err.message || 'Generation failed' });
      return null;
    }
  },

  uploadCanvasImage: async (file, position) => {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const resp = await fetch('/api/v1/creative/upload', {
        method: 'POST',
        body: formData,
      });

      if (!resp.ok) {
        throw new Error(`Upload failed with HTTP ${resp.status}`);
      }

      const asset = await resp.json();
      const canvasStore = useCanvasStore.getState();
      const existingNodes = canvasStore.nodes;
      const pos = position || {
        x: 100 + (existingNodes.length % 4) * 350,
        y: 100 + Math.floor(existingNodes.length / 4) * 380,
      };

      const cardId = `image_upload_${Date.now()}`;
      const cardData: ImageCardData = {
        assetId: asset.id,
        imageUrl: `/api/v1/assets/${asset.id}/content`,
        width: asset.width || 512,
        height: asset.height || 512,
        label: asset.filename,
      };

      const newCardNode = {
        id: cardId,
        type: 'imageCard',
        position: pos,
        data: cardData as any,
      };

      useCanvasStore.setState({
        nodes: [...existingNodes, newCardNode],
        selectedNodeId: cardId,
      });
    } catch (err: any) {
      set({ error: err.message || 'Image upload failed' });
    }
  },
}));
