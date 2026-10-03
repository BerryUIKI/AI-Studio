import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useModelHubStore, HubModel } from '../stores/useModelHubStore';

describe('useModelHubStore', () => {
  beforeEach(() => {
    useModelHubStore.setState({
      models: [],
      evaluations: {},
      hardwareSummary: null,
      selectedCategory: 'all',
      selectedArchitecture: 'all',
      searchQuery: '',
      onlyCompatible: false,
      isLoading: false,
      error: null,
    });
    vi.restoreAllMocks();
  });

  it('initializes with empty catalog and default filter values', () => {
    const state = useModelHubStore.getState();
    expect(state.models).toEqual([]);
    expect(state.selectedCategory).toBe('all');
    expect(state.onlyCompatible).toBe(false);
  });

  it('updates category and search filters', () => {
    const store = useModelHubStore.getState();
    store.setCategory('checkpoint');
    expect(useModelHubStore.getState().selectedCategory).toBe('checkpoint');

    store.setSearchQuery('flux');
    expect(useModelHubStore.getState().searchQuery).toBe('flux');

    store.setOnlyCompatible(true);
    expect(useModelHubStore.getState().onlyCompatible).toBe(true);
  });

  it('fetches catalog from API successfully', async () => {
    const mockModels: HubModel[] = [
      {
        id: 'flux-1-schnell-fp8',
        name: 'FLUX.1 [schnell] FP8',
        architecture: 'flux.1-schnell',
        category: 'checkpoint',
        version: '1.0-fp8',
        size_bytes: 11900000000,
        parameter_count: '12B',
        author: 'Black Forest Labs',
        description: 'Fast diffusion model.',
        preview_image_url: 'https://example.com/preview.webp',
        tags: ['photorealism'],
        recommended_resolution: [1024, 1024],
        min_vram_mb: 8192,
        optimal_vram_mb: 16384,
        sources: [],
        is_installed: false,
      },
    ];

    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/catalog')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ total: 1, models: mockModels }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({
          hardware_summary: {
            has_gpu: true,
            gpu_name: 'NVIDIA RTX 4090',
            vram_total_mb: 24576,
            vram_free_mb: 20000,
            ram_total_mb: 32768,
            ram_avail_mb: 24000,
          },
          evaluations: {
            'flux-1-schnell-fp8': {
              tier: 'optimal',
              tier_label: 'Optimal',
              tier_color: 'emerald',
              estimated_latency_sec: '4-8s',
              required_vram_mb: 13000,
              notes: 'Fits in VRAM',
            },
          },
        }),
      });
    });

    const store = useModelHubStore.getState();
    await store.fetchCatalog();

    const state = useModelHubStore.getState();
    expect(state.models.length).toBe(1);
    expect(state.models[0].id).toBe('flux-1-schnell-fp8');
  });
});
