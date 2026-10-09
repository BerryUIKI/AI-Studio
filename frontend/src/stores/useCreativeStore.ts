import { mediaCardFields } from '../utils/media';
import { create } from 'zustand';
import { CreativeActionRequest, CreativeActionResult, ImageCardData } from '../types/creative';
import { useCanvasStore } from './useCanvasStore';
import { useProjectStore } from './useProjectStore';
import { GenerationTask } from '../types/task';

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
  activeTaskId: string | null;
  cancellationRequested: boolean;
  generationNotice: string | null;
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
  cancelGeneration: () => Promise<void>;
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
  activeTaskId: null,
  cancellationRequested: false,
  generationNotice: null,
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

  cancelGeneration: async () => {
    const taskId = get().activeTaskId;
    if (!taskId || get().cancellationRequested) return;
    try {
      const response = await fetch(`/api/v1/tasks/${taskId}/cancel`, { method: 'POST' });
      if (!response.ok) throw new Error(`Cancellation request failed (HTTP ${response.status})`);
      const outcome: { disclaimer?: string } = await response.json();
      if (get().activeTaskId === taskId) set({ cancellationRequested: true, generationStage: 'Cancellation requested',
        generationNotice: outcome.disclaimer || 'Awaiting the execution outcome.' });
    } catch (error: unknown) {
      set({ error: error instanceof Error ? error.message : 'Cancellation request failed' });
    }
  },

  executeCreativeAction: async (override) => {
    const s = get();
    if (s.isGenerating) return null;
    const projectId = useProjectStore.getState().currentProject?.id;
    set({
      isGenerating: true,
      error: null,
      activeTaskId: null,
      cancellationRequested: false,
      generationNotice: null,
      generationStage: 'Submitting task...',
      generationProgress: 0,
    });

    const action = override?.action || (s.referenceImage ? 'img2img' : 'txt2img');
    const isSourceDependent = ['upscale', 'img2img', 'inpaint', 'img2video'].includes(action);
    const effectiveAspectRatio = isSourceDependent ? undefined : s.aspectRatio;

    const payload: CreativeActionRequest = {
      action,
      prompt: s.prompt,
      negative_prompt: s.negativePrompt,
      model: s.model,
      connection_id: s.connectionId,  // Pass stable connection_id
      engine_id: s.engineId,          // Legacy fallback for backward compatibility
      ...(effectiveAspectRatio ? { aspect_ratio: effectiveAspectRatio } : {}),
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

    if (isSourceDependent && !override?.aspect_ratio) {
      delete payload.aspect_ratio;
    }

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

    let placeholderW = 512;
    let placeholderH = 512;
    if (action === 'upscale') {
      const srcW = override?.width || s.referenceImage?.width || 512;
      const srcH = override?.height || s.referenceImage?.height || 512;
      const factor = override?.upscale_factor || 2.0;
      placeholderW = Math.round(srcW * factor);
      placeholderH = Math.round(srcH * factor);
    } else if (override?.width && override?.height) {
      placeholderW = override.width;
      placeholderH = override.height;
    } else if (s.referenceImage?.width && s.referenceImage?.height) {
      placeholderW = s.referenceImage.width;
      placeholderH = s.referenceImage.height;
    }

    const placeholderCard: ImageCardData = {
      imageUrl: s.referenceImage?.imageUrl || '',
      mediaType: isVideo ? 'video' : 'image',
      width: placeholderW,
      height: placeholderH,
      label: s.prompt,
      isGenerating: true,
      generationStage: 'Submitting task...',
      generationProgress: 0,
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

    try {
      const resp = await fetch('/api/v1/creative/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...payload, project_id: projectId }),
      });

      if (!resp.ok) {
        throw new Error(`Server returned HTTP ${resp.status}`);
      }

      const submission: { task_id: string } = await resp.json();
      set({ activeTaskId: submission.task_id });
      let result: CreativeActionResult;
      for (;;) {
        const statusResponse = await fetch(`/api/v1/creative/tasks/${submission.task_id}`, { signal: AbortSignal.timeout(30000) });
        if (!statusResponse.ok) throw new Error(`Task status unavailable (HTTP ${statusResponse.status}); task ${submission.task_id} remains in history.`);
        const task: GenerationTask = await statusResponse.json();
        if (['succeeded', 'cached'].includes(task.status)) {
          result = task.outputs as CreativeActionResult;
          if (task.metadata.cancel_requested) set({ generationNotice: 'Execution completed before cancellation could be confirmed.' });
          break;
        }
        if (['failed', 'cancelled', 'interrupted', 'outcome-unknown'].includes(task.status)) throw new Error(task.error || task.status);
        const stage = task.status === 'cancel-requested' ? 'Cancellation requested; awaiting outcome' : task.status === 'queued' ? 'Queued' : 'Running';
        set({ generationStage: stage });
        useCanvasStore.setState((state) => ({ nodes: state.nodes.map((node) => node.id === placeholderId
          ? { ...node, data: { ...node.data, generationStage: stage, generationProgress: 0 } } : node) }));
        await new Promise<void>((resolve) => setTimeout(resolve, 1000));
      }
      if (!result.success || (!result.image_url && !result.video_url)) {
        throw new Error(result.error_message || 'Generation failed');
      }

      set({
        generationStage: 'Asset ready on canvas!',
        generationProgress: 100,
      });

      const updatedCardData: ImageCardData = {
        ...mediaCardFields(result),
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

      if (useProjectStore.getState().currentProject?.id !== projectId) {
        set({ isGenerating: false, generationNotice: 'Result saved in the original project task history.' });
        return result;
      }

      useCanvasStore.getState().pushSnapshot();
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

      useCanvasStore.getState().addGenerationHistory({
        id: `gen_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
        action: s.referenceImage ? (s.inpaintModalOpen ? 'inpaint' : 'img2img') : 'txt2img',
        prompt: s.prompt,
        timestamp: new Date().toISOString(),
        assetId: result.asset_id,
        imageUrl: result.image_url || result.video_url,
        videoUrl: result.video_url,
        provenance: result.provenance,
      });

      set({ isGenerating: false });
      return result;
    } catch (err: unknown) {
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

      let resolvedWidth = typeof asset.width === 'number' && asset.width > 0 ? asset.width : undefined;
      let resolvedHeight = typeof asset.height === 'number' && asset.height > 0 ? asset.height : undefined;

      if (!resolvedWidth || !resolvedHeight) {
        try {
          if (typeof createImageBitmap === 'function') {
            const bmp = await createImageBitmap(file);
            resolvedWidth = resolvedWidth || bmp.width;
            resolvedHeight = resolvedHeight || bmp.height;
            bmp.close();
          } else if (typeof Image !== 'undefined') {
            const dims = await new Promise<{ width: number; height: number }>((resolve, reject) => {
              const img = new Image();
              const objectUrl = URL.createObjectURL(file);
              img.onload = () => {
                URL.revokeObjectURL(objectUrl);
                resolve({ width: img.naturalWidth, height: img.naturalHeight });
              };
              img.onerror = () => {
                URL.revokeObjectURL(objectUrl);
                reject();
              };
              img.src = objectUrl;
            });
            resolvedWidth = resolvedWidth || dims.width;
            resolvedHeight = resolvedHeight || dims.height;
          }
        } catch {
          // Fallback if client-side decoding fails
        }
      }

      const cardId = `image_upload_${Date.now()}`;
      const cardData: ImageCardData = {
        ...mediaCardFields(asset),
        assetId: asset.id,
        imageUrl: `/api/v1/assets/${asset.id}/content`,
        width: resolvedWidth || 512,
        height: resolvedHeight || 512,
        label: asset.filename,
      };

      const newCardNode = {
        id: cardId,
        type: 'imageCard',
        position: pos,
        data: cardData,
      };

      useCanvasStore.getState().pushSnapshot();
      useCanvasStore.setState({
        nodes: [...useCanvasStore.getState().nodes, newCardNode],
        selectedNodeId: cardId,
      });
      useCanvasStore.getState().notifyCanvasChange();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Image upload failed';
      set({ error: message });
    }
  },
}));
