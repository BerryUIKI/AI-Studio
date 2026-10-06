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
  connectionId: string;  // Stable connection ID (e.g., "comfyui-managed", "webui-managed")
  engineId: string;      // Legacy field - deprecated
  model: string;
  referenceImage: ImageCardData | null;
  inpaintModalOpen: boolean;
  upscaleModalOpen: boolean;
  videoModalOpen: boolean;
  fps: number;
  numFrames: number;
  denoise: number;
  motionBucketId: number;
  durationSeconds: number;
  isGenerating: boolean;
  generationStage: string;
  generationProgress: number;
  error: string | null;

  setPrompt: (prompt: string) => void;
  setNegativePrompt: (np: string) => void;
  setAspectRatio: (ar: string) => void;
  setSteps: (steps: number) => void;
  setCfgScale: (cfg: number) => void;
  setDenoise: (denoise: number) => void;
  setSeed: (seed: number) => void;
  setConnectionId: (id: string) => void;
  setEngineId: (id: string) => void;  // Legacy - deprecated
  setModel: (m: string) => void;
  setReferenceImage: (img: ImageCardData | null) => void;
  setFps: (fps: number) => void;
  setNumFrames: (frames: number) => void;
  setMotionBucketId: (mb: number) => void;
  openInpaint: (img: ImageCardData) => void;
  openUpscale: (img: ImageCardData) => void;
  openImg2Video: (img: ImageCardData) => void;
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
  denoise: 0.75,
  seed: -1,
  connectionId: 'comfyui-managed',  // Default to managed ComfyUI connection
  engineId: 'managed_comfyui',      // Legacy field for backward compatibility
  model: 'v1-5-pruned-emaonly.safetensors',
  referenceImage: null,
  inpaintModalOpen: false,
  upscaleModalOpen: false,
  videoModalOpen: false,
  fps: 16,
  numFrames: 25,
  motionBucketId: 127,
  durationSeconds: 3.0,
  isGenerating: false,
  generationStage: 'Idle',
  generationProgress: 0,
  error: null,

  setPrompt: (prompt) => set({ prompt }),
  setNegativePrompt: (negativePrompt) => set({ negativePrompt }),
  setAspectRatio: (aspectRatio) => set({ aspectRatio }),
  setSteps: (steps) => set({ steps }),
  setCfgScale: (cfgScale) => set({ cfgScale }),
  setDenoise: (denoise) => set({ denoise }),
  setSeed: (seed) => set({ seed }),
  setConnectionId: (connectionId) => set({ connectionId }),
  setEngineId: (engineId) => {
    // Map legacy engine_id to stable connection_id
    const connectionIdMap: Record<string, string> = {
      'managed_comfyui': 'comfyui-managed',
      'comfyui': 'comfyui-managed',
      'managed_webui': 'webui-managed',
      'webui': 'webui-managed',
    };
    const connectionId = connectionIdMap[engineId] || engineId;
    set({ engineId, connectionId });
  },
  setModel: (model) => set({ model }),
  setReferenceImage: (referenceImage) => set({ referenceImage }),
  setFps: (fps) => set({ fps }),
  setNumFrames: (numFrames) => set({ numFrames }),
  setMotionBucketId: (motionBucketId) => set({ motionBucketId }),
  openInpaint: (img) => set({ referenceImage: img, inpaintModalOpen: true }),
  openUpscale: (img) => set({ referenceImage: img, upscaleModalOpen: true }),
  openImg2Video: (img) => set({ referenceImage: img, videoModalOpen: true }),
  closeModals: () => set({ inpaintModalOpen: false, upscaleModalOpen: false, videoModalOpen: false }),
  randomizeSeed: () => set({ seed: Math.floor(Math.random() * 2147483647) }),

  executeCreativeAction: async (override) => {
    const s = get();
    set({
      isGenerating: true,
      error: null,
      generationStage: 'Preparing execution & checking cache...',
      generationProgress: 15,
    });

    const action = override?.action || (s.referenceImage ? 'img2img' : 'txt2img');
    const payload: CreativeActionRequest = {
      action,
      prompt: s.prompt,
      negative_prompt: s.negativePrompt,
      model: s.model,
      connection_id: s.connectionId,  // Pass stable connection_id
      engine_id: s.engineId,          // Legacy fallback for backward compatibility
      aspect_ratio: s.aspectRatio,
      steps: s.steps,
      cfg_scale: s.cfgScale,
      denoise: s.denoise,
      seed: s.seed,
      input_image_id: s.referenceImage?.assetId,
      fps: s.fps,
      num_frames: s.numFrames,
      motion_bucket_id: s.motionBucketId,
      duration_seconds: s.durationSeconds,
      ...override,
    };

    // Prepare placeholder card on canvas
    const canvasStore = useCanvasStore.getState();
    const existingNodes = canvasStore.nodes;
    const isVideo = Boolean(action === 'txt2video' || action === 'img2video');
    const placeholderId = `${isVideo ? 'video' : 'image'}_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
    
    // Position adjacent to reference card or in next grid slot
    let posX = 80 + (existingNodes.length % 5) * 360;
    let posY = 80 + Math.floor(existingNodes.length / 5) * 440;
    if (s.referenceImage?.assetId) {
      const refNode = existingNodes.find((n) => n.data?.assetId === s.referenceImage?.assetId);
      if (refNode) {
        posX = refNode.position.x + 360;
        posY = refNode.position.y;
      }
    }

    const placeholderCard: ImageCardData = {
      imageUrl: s.referenceImage?.imageUrl || '',
      mediaType: isVideo ? 'video' : 'image',
      width: 512,
      height: 512,
      label: s.prompt,
      isGenerating: true,
      generationStage: 'Preparing parameters...',
      generationProgress: 20,
    };

    useCanvasStore.setState({
      nodes: [
        ...existingNodes,
        {
          id: placeholderId,
          type: 'imageCard',
          position: { x: posX, y: posY },
          data: placeholderCard,
        },
      ],
      selectedNodeId: placeholderId,
    });

    // Simulated progress tick timer for fine-grained UX feedback
    const stageTimer = setInterval(() => {
      const curr = get().generationProgress;
      if (curr < 85) {
        let nextStage = 'Sampling latent diffusion steps...';
        if (curr < 40) nextStage = 'Loading model checkpoint & latents...';
        else if (curr < 75) nextStage = `Denoising step ${Math.round((curr / 85) * s.steps)}/${s.steps}...`;
        else nextStage = 'Decoding VAE latent...';

        const nextProgress = Math.min(85, curr + 12);
        set({ generationProgress: nextProgress, generationStage: nextStage });

        // Update placeholder card
        useCanvasStore.setState((state) => ({
          nodes: state.nodes.map((node) => {
            if (node.id === placeholderId) {
              return {
                ...node,
                data: {
                  ...node.data,
                  generationProgress: nextProgress,
                  generationStage: nextStage,
                },
              };
            }
            return node;
          }),
        }));
      }
    }, 450);

    try {
      const resp = await fetch('/api/v1/creative/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      clearInterval(stageTimer);

      if (!resp.ok) {
        throw new Error(`Server returned HTTP ${resp.status}`);
      }

      const result: CreativeActionResult = await resp.json();
      if (!result.success || (!result.image_url && !result.video_url)) {
        throw new Error(result.error_message || 'Generation failed');
      }

      set({
        generationStage: 'Asset ready on canvas!',
        generationProgress: 100,
      });

      const updatedCardData: ImageCardData = {
        assetId: result.asset_id,
        imageUrl: result.image_url || result.video_url || '',
        videoUrl: result.video_url,
        mediaType: isVideo ? 'video' : 'image',
        width: result.width,
        height: result.height,
        provenance: result.provenance,
        label: result.provenance?.prompt || s.prompt,
        isGenerating: false,
        generationStage: 'Done',
        generationProgress: 100,
      };

      useCanvasStore.setState((state) => ({
        nodes: state.nodes.map((node) => {
          if (node.id === placeholderId) {
            return {
              ...node,
              data: updatedCardData,
            };
          }
          return node;
        }),
        selectedNodeId: placeholderId,
      }));

      set({ isGenerating: false });
      return result;
    } catch (err: unknown) {
      clearInterval(stageTimer);
      // Remove failed placeholder card from canvas
      useCanvasStore.setState((state) => ({
        nodes: state.nodes.filter((node) => node.id !== placeholderId),
      }));
      set({
        isGenerating: false,
        error: err instanceof Error ? err.message : 'Generation failed',
        generationStage: 'Failed',
        generationProgress: 0,
      });
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
        data: cardData,
      };

      useCanvasStore.setState({
        nodes: [...existingNodes, newCardNode],
        selectedNodeId: cardId,
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Image upload failed';
      set({ error: message });
    }
  },
}));
