# Berry AI Studio Model Hub — API & State Specification

Date: 2026-10-03  
Status: Approved Interface Specification  
Target Version: v0.2.0  
Governing Documents: [`docs/MODEL_HUB_PRD.md`](MODEL_HUB_PRD.md), [`docs/MODEL_HUB_UI_SPEC.md`](MODEL_HUB_UI_SPEC.md).

---

## 1. REST API Specification

### 1.1 `GET /api/v1/models/hub/catalog`
Retrieve curated model catalog with optional filtering.

- **Query Parameters**:
  - `category` (optional, string): Filter by category (`checkpoint`, `lora`, `controlnet`, `upscaler`, `vae`).
  - `architecture` (optional, string): Filter by base architecture (`sd-1.5`, `sdxl`, `flux.1-schnell`, `flux.1-dev`, `all`).
  - `query` (optional, string): Search term matching name, tags, or description.
- **Response**: `200 OK`
```json
{
  "total": 12,
  "models": [
    {
      "id": "flux-1-schnell-fp8",
      "name": "FLUX.1 [schnell] (FP8 Quantized)",
      "architecture": "flux.1-schnell",
      "category": "checkpoint",
      "version": "1.0-fp8",
      "size_bytes": 12800000000,
      "parameter_count": "12B",
      "quantization": "FP8",
      "author": "Black Forest Labs",
      "description": "High-speed photorealism in 4 steps.",
      "preview_image_url": "/assets/hub/flux_schnell.webp",
      "tags": ["photorealism", "text-rendering"],
      "recommended_resolution": [1024, 1024],
      "min_vram_mb": 8192,
      "optimal_vram_mb": 16384,
      "is_installed": false,
      "installed_path": null
    }
  ]
}
```

---

### 1.2 `POST /api/v1/models/hub/evaluate`
Evaluate hardware compatibility across requested models.

- **Request Body**:
```json
{
  "model_ids": ["flux-1-schnell-fp8", "flux-1-dev-fp16", "sd-1.5-base"]
}
```
- **Response**: `200 OK`
```json
{
  "hardware_summary": {
    "gpu_name": "NVIDIA GeForce RTX 4070",
    "vram_total_mb": 12288,
    "vram_free_mb": 10240,
    "ram_total_mb": 32768,
    "ram_avail_mb": 18432
  },
  "evaluations": {
    "flux-1-schnell-fp8": {
      "tier": "optimal",
      "tier_label": "极致流畅 (Optimal)",
      "tier_color": "emerald",
      "estimated_latency_sec": "4-8s",
      "required_vram_mb": 12200,
      "notes": "Model fits comfortably in dedicated VRAM without CPU paging."
    },
    "flux-1-dev-fp16": {
      "tier": "playable_offload",
      "tier_label": "需共享内存 (RAM Offload)",
      "tier_color": "amber",
      "estimated_latency_sec": "25-40s",
      "required_vram_mb": 24000,
      "notes": "Dedicated VRAM is tight; execution requires ~12GB CPU RAM offloading."
    }
  }
}
```

---

### 1.3 `POST /api/v1/models/hub/download`
Initiate an asynchronous resumable download task.

- **Request Body**:
```json
{
  "model_id": "flux-1-schnell-fp8",
  "target_engine": "comfyui",
  "mirror_preset": "china_mainland"
}
```
- **Response**: `202 Accepted`
```json
{
  "task_id": "dl_task_9812",
  "model_id": "flux-1-schnell-fp8",
  "model_name": "FLUX.1 [schnell] (FP8 Quantized)",
  "target_path": "models/checkpoints/flux1-schnell-fp8.safetensors",
  "status": "downloading",
  "total_bytes": 12800000000,
  "downloaded_bytes": 0,
  "progress_pct": 0.0,
  "speed_bps": 0,
  "eta_seconds": null
}
```

---

### 1.4 `GET /api/v1/models/hub/tasks`
Fetch live download tasks queue and historical completions.

- **Response**: `200 OK`
```json
{
  "tasks": [
    {
      "task_id": "dl_task_9812",
      "model_id": "flux-1-schnell-fp8",
      "model_name": "FLUX.1 [schnell] (FP8 Quantized)",
      "target_engine": "comfyui",
      "target_path": "models/checkpoints/flux1-schnell-fp8.safetensors",
      "status": "downloading",
      "total_bytes": 12800000000,
      "downloaded_bytes": 4500000000,
      "progress_pct": 35.1,
      "speed_bps": 42500000,
      "eta_seconds": 195,
      "error_message": null
    }
  ]
}
```

---

## 2. Frontend Zustand Store Contracts

### 2.1 `useModelHubStore`
```typescript
export interface HubModel {
  id: string;
  name: string;
  architecture: string;
  category: 'checkpoint' | 'lora' | 'controlnet' | 'upscaler' | 'vae';
  version: string;
  size_bytes: number;
  parameter_count: string;
  quantization?: string;
  author: string;
  description: string;
  preview_image_url: string;
  tags: string[];
  min_vram_mb: number;
  optimal_vram_mb: number;
  is_installed: boolean;
  installed_path?: string | null;
}

export type CompatibilityTier = 'optimal' | 'playable_offload' | 'heavy_paging' | 'unsupported';

export interface ModelEvaluation {
  tier: CompatibilityTier;
  tier_label: string;
  tier_color: 'emerald' | 'amber' | 'orange' | 'rose';
  estimated_latency_sec: string;
  required_vram_mb: number;
  notes: string;
}

interface ModelHubState {
  models: HubModel[];
  evaluations: Record<string, ModelEvaluation>;
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
```

### 2.2 `useDownloadStore`
```typescript
export interface DownloadTask {
  task_id: string;
  model_id: string;
  model_name: string;
  target_engine: string;
  target_path: string;
  status: 'pending' | 'downloading' | 'paused' | 'completed' | 'failed' | 'cancelled';
  total_bytes: number;
  downloaded_bytes: number;
  progress_pct: number;
  speed_bps: number;
  eta_seconds: number | null;
  error_message?: string | null;
}

interface DownloadState {
  tasks: DownloadTask[];
  isDrawerOpen: boolean;
  activeCount: number;

  setIsDrawerOpen: (open: boolean) => void;
  fetchTasks: () => Promise<void>;
  startDownload: (modelId: string, engine: string) => Promise<string>;
  pauseDownload: (taskId: string) => Promise<void>;
  resumeDownload: (taskId: string) => Promise<void>;
  cancelDownload: (taskId: string) => Promise<void>;
}
```
