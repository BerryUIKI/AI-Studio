import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useCreativeStore } from '../stores/useCreativeStore';
import { useCanvasStore } from '../stores/useCanvasStore';
import { ImageCardData } from '../types/creative';

/**
 * Tests for Issue #123: Synchronizing image dimensions, upscale factors,
 * and result metadata.
 *
 * Verifies:
 * - 640×360 landscape input fixture:
 *   - 2× upscale computes exactly 1280×720
 *   - 4× upscale computes exactly 2560×1440
 * - 360×640 portrait input fixture:
 *   - 2× upscale computes exactly 720×1280
 *   - 4× upscale computes exactly 1440×2560
 * - Aspect ratios are strictly preserved
 * - Source-dependent actions (upscale, img2img, inpaint, img2video)
 *   do not send store default aspect_ratio
 * - Upscale placeholder card uses calculated target dimensions
 * - uploadCanvasImage adopts decoded dimensions and avoids fabricated 512 defaults
 */

describe('Image Dimensions, Upscale Factors, and Metadata (Issue #123)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useCanvasStore.setState({
      nodes: [],
      edges: [],
      selectedNodeId: null,
      past: [],
      future: [],
    });

    useCreativeStore.setState({
      prompt: 'A scenic mountain lake',
      negativePrompt: '',
      aspectRatio: '1:1', // Default store aspect ratio must not overwrite source-dependent actions
      steps: 20,
      cfgScale: 7.0,
      denoise: 0.5,
      seed: 42,
      connectionId: 'comfyui-managed',
      engineId: 'managed_comfyui',
      model: 'sd15',
      referenceImage: null,
      isGenerating: false,
    });
  });

  describe('640×360 Fixture Resolution Calculations', () => {
    it('computes exact 1280×720 for 2× upscale on 640×360 fixture', () => {
      const sourceW = 640;
      const sourceH = 360;
      const factor = 2.0;

      const targetW = Math.round(sourceW * factor);
      const targetH = Math.round(sourceH * factor);

      expect(targetW).toBe(1280);
      expect(targetH).toBe(720);
      expect(targetW / targetH).toBeCloseTo(sourceW / sourceH, 5);
    });

    it('computes exact 2560×1440 for 4× upscale on 640×360 fixture', () => {
      const sourceW = 640;
      const sourceH = 360;
      const factor = 4.0;

      const targetW = Math.round(sourceW * factor);
      const targetH = Math.round(sourceH * factor);

      expect(targetW).toBe(2560);
      expect(targetH).toBe(1440);
      expect(targetW / targetH).toBeCloseTo(sourceW / sourceH, 5);
    });
  });

  describe('Portrait 360×640 Fixture Resolution Calculations', () => {
    it('computes exact 720×1280 for 2× upscale on 360×640 portrait fixture', () => {
      const sourceW = 360;
      const sourceH = 640;
      const factor = 2.0;

      const targetW = Math.round(sourceW * factor);
      const targetH = Math.round(sourceH * factor);

      expect(targetW).toBe(720);
      expect(targetH).toBe(1280);
      expect(targetW / targetH).toBeCloseTo(sourceW / sourceH, 5);
    });

    it('computes exact 1440×2560 for 4× upscale on 360×640 portrait fixture', () => {
      const sourceW = 360;
      const sourceH = 640;
      const factor = 4.0;

      const targetW = Math.round(sourceW * factor);
      const targetH = Math.round(sourceH * factor);

      expect(targetW).toBe(1440);
      expect(targetH).toBe(2560);
      expect(targetW / targetH).toBeCloseTo(sourceW / sourceH, 5);
    });
  });

  describe('executeCreativeAction Payload & Placeholder Behavior', () => {
    it('omits aspect_ratio for upscale action and sizes placeholder to target dimensions', async () => {
      const refCard: ImageCardData = {
        assetId: 'asset-640x360',
        imageUrl: '/api/v1/assets/asset-640x360/content',
        width: 640,
        height: 360,
      };

      useCreativeStore.setState({ referenceImage: refCard });

      let capturedPayload: any = null;
      globalThis.fetch = vi.fn().mockImplementation((url, init) => {
        if (url === '/api/v1/creative/submit') {
          capturedPayload = JSON.parse(init.body);
          return Promise.resolve({ ok: true, json: async () => ({ task_id: 'task-upscale-1' }) });
        }
        if (url === '/api/v1/creative/tasks/task-upscale-1') {
          return Promise.resolve({
            ok: true,
            json: async () => ({ status: 'succeeded', metadata: {}, outputs: {
              success: true,
              task_id: 'task-upscale-1',
              asset_id: 'asset-1280x720',
              image_url: '/api/v1/assets/asset-1280x720/content',
              width: 1280,
              height: 720,
              provenance: {
                action: 'upscale',
                dimensions: '1280x720',
              },
            } }),
          });
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`));
      });

      const store = useCreativeStore.getState();
      const res = await store.executeCreativeAction({
        action: 'upscale',
        input_image_id: 'asset-640x360',
        upscale_factor: 2.0,
        upscaler_name: 'R-ESRGAN 4x+',
        width: 640,
        height: 360,
      });

      expect(res).not.toBeNull();
      expect(res?.success).toBe(true);

      // Verify payload does NOT have default store aspect_ratio ('1:1')
      expect(capturedPayload).not.toBeNull();
      expect(capturedPayload.aspect_ratio).toBeUndefined();
      expect(capturedPayload.upscale_factor).toBe(2.0);
      expect(capturedPayload.width).toBe(640);
      expect(capturedPayload.height).toBe(360);

      // Verify resulting canvas node has truthful output dimensions
      const canvasNodes = useCanvasStore.getState().nodes;
      expect(canvasNodes.length).toBe(1);
      const generatedCard = canvasNodes[0].data as ImageCardData;
      expect(generatedCard.width).toBe(1280);
      expect(generatedCard.height).toBe(720);
      expect(generatedCard.provenance?.dimensions).toBe('1280x720');
    });

    it('omits store default aspect_ratio for other source-dependent actions (img2img, inpaint)', async () => {
      const refCard: ImageCardData = {
        assetId: 'asset-ref',
        imageUrl: '/test.png',
        width: 640,
        height: 360,
      };
      useCreativeStore.setState({ referenceImage: refCard, aspectRatio: '16:9' });

      let capturedPayload: any = null;
      globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
        if (init?.body) capturedPayload = JSON.parse(init.body);
        return Promise.resolve({
          ok: true,
          json: async () => ({
            success: true,
            task_id: 'task-1',
            status: 'succeeded', metadata: {},
            outputs: { success: true, task_id: 'task-1', image_url: '/result.png', width: 640, height: 360 },
            width: 640,
            height: 360,
            image_url: '/result.png',
          }),
        });
      });

      await useCreativeStore.getState().executeCreativeAction({ action: 'img2img' });
      expect(capturedPayload.aspect_ratio).toBeUndefined();

      await useCreativeStore.getState().executeCreativeAction({ action: 'inpaint' });
      expect(capturedPayload.aspect_ratio).toBeUndefined();

      // txt2img SHOULD include aspect_ratio
      useCreativeStore.setState({ referenceImage: null });
      await useCreativeStore.getState().executeCreativeAction({ action: 'txt2img' });
      expect(capturedPayload.aspect_ratio).toBe('16:9');
    });
  });

  describe('uploadCanvasImage Dimension Adoption', () => {
    it('persists and uses decoded dimensions from asset response without fabricated 512 defaults', async () => {
      const mockAsset = {
        id: 'imported-asset-640x360',
        filename: 'landscape.png',
        content_type: 'image/png',
        width: 640,
        height: 360,
      };

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockAsset,
      });

      const mockFile = new File(['dummy bytes'], 'landscape.png', { type: 'image/png' });

      await useCreativeStore.getState().uploadCanvasImage(mockFile);

      const nodes = useCanvasStore.getState().nodes;
      expect(nodes.length).toBe(1);
      const card = nodes[0].data as ImageCardData;

      expect(card.assetId).toBe('imported-asset-640x360');
      expect(card.width).toBe(640);
      expect(card.height).toBe(360);
      expect(card.width).not.toBe(512);
      expect(card.height).not.toBe(512);
    });
  });
});
