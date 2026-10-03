# Berry AI Studio Model Hub — Implementation Milestones (MH-M1 to MH-M5)

Date: 2026-10-03  
Status: Approved Implementation Plan  
Parent PRD: [`docs/MODEL_HUB_PRD.md`](MODEL_HUB_PRD.md)  
Governing Documents: [`docs/ROADMAP_POST_V0_1.md`](ROADMAP_POST_V0_1.md), [`docs/MODEL_HUB_UI_SPEC.md`](MODEL_HUB_UI_SPEC.md), [`docs/MODEL_HUB_API_SPEC.md`](MODEL_HUB_API_SPEC.md).

---

## Overview

The Model Hub is developed in 5 sequential, incremental milestones following the strict documentation-first and GitFlow rules:

```
MH-M1 (Navigation Entry & Model Hub Shell)
  └─→ MH-M2 (Curated Catalog & 4-Tier Hardware Evaluation Engine)
        ├─→ MH-M3 (Interactive Cards & Compatibility Tooltip UI)
        └─→ MH-M4 (Multi-Mirror Resumable Download Engine)
              └─→ MH-M5 (Download Drawer, Floating Widget & E2E Verification)
```

---

## MH-M1 — Navigation Entry & Model Hub Shell
**Goal**: Add the top-level "📦 Model Hub" view to the primary navigation shell with state preservation across view switches.
**Status**: ✅ Completed (Implemented and Verified)

### Deliverables
| # | Task | Target Files |
| :--- | :--- | :--- |
| 1 | Extend `useNavigationStore` active view union to include `'models'` | `frontend/src/stores/useNavigationStore.ts` |
| 2 | Update `GlobalNavRail` to render Model Hub icon button with active highlight | `frontend/src/components/navigation/GlobalNavRail.tsx` |
| 3 | Create initial `ModelHubView` shell and register in `ViewContainer` | `frontend/src/components/hub/ModelHubView.tsx`, `frontend/src/components/navigation/ViewContainer.tsx` |
| 4 | Add unit tests verifying navigation to `'models'` view | `frontend/src/tests/navigationStore.test.ts` |

---

## MH-M2 — Curated Catalog & 4-Tier Hardware Evaluation Engine
**Goal**: Implement backend catalog registry and hardware runnability assessment.
**Status**: ✅ Completed (Implemented and Verified)

### Deliverables
| # | Task | Target Files |
| :--- | :--- | :--- |
| 1 | Create Pydantic schemas for Hub models and hardware evaluations | `backend/app/schemas/model_hub.py` |
| 2 | Create `HubCatalog` registry with curated high-speed and quality open weights (FLUX.1 schnell FP8, SDXL Turbo, SD 1.5, ESRGAN upscalers, LoRAs) | `backend/app/storage/hub_catalog.py` |
| 3 | Implement 4-tier hardware rating algorithm in `hardware_evaluator.py`: Optimal (🟢), Playable / RAM Offload (🟡), Heavy Paging (🟠), Unsupported / OOM (🔴) | `backend/app/runtime/hardware_evaluator.py` |
| 4 | Expose REST endpoints `GET /api/v1/models/hub/catalog` and `POST /api/v1/models/hub/evaluate` | `backend/app/main.py` |
| 5 | Unit tests for hardware rating formula and endpoint conformance | `backend/tests/test_model_hub_eval.py` |

---

## MH-M3 — Interactive Cards & Compatibility Tooltip UI
**Goal**: Build the responsive card grid with hardware rating badges and detailed diagnostic popovers.
**Status**: ✅ Completed (Implemented and Verified)

### Deliverables
| # | Task | Target Files |
| :--- | :--- | :--- |
| 1 | Implement `useModelHubStore` with filtering, search query, and hardware evaluation fetching | `frontend/src/stores/useModelHubStore.ts` |
| 2 | Create `HubModelCard` component with artwork preview, architecture tags, size in GB, and install actions | `frontend/src/components/hub/HubModelCard.tsx` |
| 3 | Implement `CompatibilityBadge` and `HardwareDiagnosticTooltip` showing detailed memory footprint vs host VRAM/RAM analysis | `frontend/src/components/hub/CompatibilityBadge.tsx` |
| 4 | Add search and category filter bar (All, Checkpoint, LoRA, ControlNet, Upscaler) | `frontend/src/components/hub/ModelHubView.tsx` |
| 5 | Frontend tests for model hub store and filtering logic | `frontend/src/tests/modelHubStore.test.ts` |

---

## MH-M4 — Multi-Mirror Resumable Download Engine
**Status**: ✅ Completed (Implemented and Verified)
**Goal**: Implement background downloader with mirror fallback, chunk resumption, atomic destination placement, and inventory hot-rescan.

### Deliverables
| # | Task | Target Files |
| :--- | :--- | :--- |
| 1 | Create `ModelDownloader` service supporting multi-part resumable HTTP streaming and mirror acceleration (`hf-mirror`, ModelScope) | `backend/app/runtime/model_downloader.py` |
| 2 | Add engine target directory resolver: routes Checkpoints $\rightarrow$ `models/checkpoints/`, LoRAs $\rightarrow$ `models/loras/`, etc. | `backend/app/runtime/model_downloader.py` |
| 3 | Implement download task lifecycle: pause, resume, cancel, and SHA-256 verification | `backend/app/runtime/model_downloader.py` |
| 4 | Expose REST endpoints: `POST /download`, `GET /tasks`, `POST /tasks/{id}/pause`, `POST /tasks/{id}/resume`, `DELETE /tasks/{id}` | `backend/app/main.py` |
| 5 | Unit tests for downloader resumption, mirror selection, and file placement | `backend/tests/test_model_downloader.py` |

---

## MH-M5 — Download Drawer, Floating Widget & E2E Verification
**Status**: ✅ Completed (Implemented and Verified)
**Goal**: Deliver the user-facing download management UI and complete end-to-end integration.

### Deliverables
| # | Task | Target Files |
| :--- | :--- | :--- |
| 1 | Create `useDownloadStore` polling active download tasks and transfer metrics | `frontend/src/stores/useDownloadStore.ts` |
| 2 | Implement `FloatingDownloadWidget` (bottom-right pill showing total speed and progress) | `frontend/src/components/hub/FloatingDownloadWidget.tsx` |
| 3 | Implement `DownloadManagerDrawer` with active tasks list, pause/resume/cancel controls, and speed gauges | `frontend/src/components/hub/DownloadManagerDrawer.tsx` |
| 4 | Wire auto-refresh of local model inventory and instant canvas availability | `frontend/src/App.tsx` |
| 5 | Vitest integration tests for download store and drawer UI | `frontend/src/tests/downloadStore.test.ts` |
| 6 | Comprehensive documentation update and release evidence compilation | `docs/` |

---

## Summary Timeline

| Milestone | Scope | Estimated Effort |
| :--- | :--- | :--- |
| **MH-M1** | Navigation Entry & Hub Shell | 1 day |
| **MH-M2** | Curated Catalog & Hardware Evaluation Engine | 2 days |
| **MH-M3** | Interactive Cards & Compatibility Tooltip UI | 2 days |
| **MH-M4** | Multi-Mirror Resumable Download Engine | 3 days |
| **MH-M5** | Download Drawer, Floating Widget & Testing | 2 days |
| **Total** | **End-to-End Model Hub & Downloader** | **~10 working days** |
