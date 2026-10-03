import { describe, it, expect, beforeEach } from 'vitest';
import { useCreativeStore } from '../stores/useCreativeStore';

describe('useCreativeStore', () => {
  beforeEach(() => {
    useCreativeStore.setState({
      prompt: 'test prompt',
      negativePrompt: 'test negative',
      aspectRatio: '1:1',
      steps: 20,
      cfgScale: 7.0,
      seed: 42,
      fps: 16,
      numFrames: 25,
      inpaintModalOpen: false,
      upscaleModalOpen: false,
      videoModalOpen: false,
      referenceImage: null,
    });
  });

  it('updates prompt and aspect ratio correctly', () => {
    const store = useCreativeStore.getState();
    store.setPrompt('A vibrant sunset over the ocean');
    store.setAspectRatio('16:9');

    expect(useCreativeStore.getState().prompt).toBe('A vibrant sunset over the ocean');
    expect(useCreativeStore.getState().aspectRatio).toBe('16:9');
  });

  it('updates video generation parameters', () => {
    const store = useCreativeStore.getState();
    store.setFps(24);
    store.setNumFrames(48);
    store.setMotionBucketId(150);

    const state = useCreativeStore.getState();
    expect(state.fps).toBe(24);
    expect(state.numFrames).toBe(48);
    expect(state.motionBucketId).toBe(150);
  });

  it('handles modal state transitions cleanly', () => {
    const store = useCreativeStore.getState();
    const mockImage = {
      assetId: 'asset-1',
      imageUrl: 'http://127.0.0.1:8000/assets/test.png',
      width: 512,
      height: 512,
      provenance: {
        action: 'txt2img' as const,
        prompt: 'test',
        model: 'sd15',
        engine_id: 'managed_comfyui',
        seed: 1234,
        steps: 20,
        cfg_scale: 7,
        dimensions: '512x512',
        created_at: new Date().toISOString(),
      },
    };

    store.openInpaint(mockImage);
    expect(useCreativeStore.getState().inpaintModalOpen).toBe(true);
    expect(useCreativeStore.getState().referenceImage?.assetId).toBe('asset-1');

    store.closeModals();
    expect(useCreativeStore.getState().inpaintModalOpen).toBe(false);
  });

  it('randomizes seed to a non-negative number', () => {
    const store = useCreativeStore.getState();
    store.randomizeSeed();
    const state = useCreativeStore.getState();
    expect(state.seed).toBeGreaterThanOrEqual(0);
  });
});
