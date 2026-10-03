import { create } from 'zustand';

export interface ModelSource {
  name: string;
  url: string;
}

export interface HubModel {
  id: string;
  name: string;
  architecture: string;
  category: string;
  version: string;
  size_bytes: number;
  parameter_count: string;
  quantization?: string | null;
  author: string;
  description: string;
  preview_image_url: string;
  tags: string[];
  recommended_resolution: [number, number];
  min_vram_mb: number;
  optimal_vram_mb: number;
  sources: ModelSource[];
  sha256?: string | null;
  is_installed: boolean;
  installed_path?: string | null;
}

export type CompatibilityTier = 'optimal' | 'playable_offload' | 'heavy_paging' | 'unsupported';

export interface ModelEvaluation {
  tier: CompatibilityTier;
  tier_label: string;
  tier_color: string;
  estimated_latency_sec: string;
  required_vram_mb: number;
  notes: string;
}

export interface HardwareSummary {
  has_gpu: boolean;
  gpu_name: string;
  vram_total_mb: number;
  vram_free_mb: number;
  ram_total_mb: number;
  ram_avail_mb: number;
}

interface ModelHubState {
  models: HubModel[];
  evaluations: Record<string, ModelEvaluation>;
  hardwareSummary: HardwareSummary | null;
  selectedCategory: string;
  selectedArchitecture: string;
  searchQuery: string;
  onlyCompatible: boolean;
  isLoading: boolean;
  error: string | null;

  setCategory: (category: string) => void;
  setArchitecture: (arch: string) => void;
  setSearchQuery: (query: string) => void;
  setOnlyCompatible: (only: boolean) => void;
  fetchCatalog: () => Promise<void>;
  evaluateHardware: () => Promise<void>;
}

export const useModelHubStore = create<ModelHubState>((set, get) => ({
  models: [],
  evaluations: {},
  hardwareSummary: null,
  selectedCategory: 'all',
  selectedArchitecture: 'all',
  searchQuery: '',
  onlyCompatible: false,
  isLoading: false,
  error: null,

  setCategory: (category) => set({ selectedCategory: category }),
  setArchitecture: (arch) => set({ selectedArchitecture: arch }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setOnlyCompatible: (only) => set({ onlyCompatible: only }),

  fetchCatalog: async () => {
    try {
      set({ isLoading: true, error: null });
      const { selectedCategory, selectedArchitecture, searchQuery } = get();
      const params = new URLSearchParams();
      if (selectedCategory && selectedCategory !== 'all') params.set('category', selectedCategory);
      if (selectedArchitecture && selectedArchitecture !== 'all') params.set('architecture', selectedArchitecture);
      if (searchQuery.trim()) params.set('query', searchQuery.trim());

      const res = await fetch(`/api/v1/models/hub/catalog?${params.toString()}`);
      if (!res.ok) {
        throw new Error(`Failed to load catalog: ${res.statusText}`);
      }
      const data = await res.json();
      set({ models: data.models || [], isLoading: false });

      // Automatically evaluate hardware for loaded models
      get().evaluateHardware();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error loading catalog';
      set({ error: msg, isLoading: false });
    }
  },

  evaluateHardware: async () => {
    try {
      const { models } = get();
      if (models.length === 0) return;

      const modelIds = models.map((m) => m.id);
      const res = await fetch('/api/v1/models/hub/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_ids: modelIds }),
      });

      if (res.ok) {
        const data = await res.json();
        set({
          hardwareSummary: data.hardware_summary,
          evaluations: data.evaluations || {},
        });
      }
    } catch {
      // Hardware evaluation failure shouldn't block browsing
    }
  },
}));
