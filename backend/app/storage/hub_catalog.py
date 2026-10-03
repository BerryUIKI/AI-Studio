"""Curated Model Hub Catalog Registry for Berry AI Studio (MH-M2)."""

from typing import List, Optional
from app.schemas.model_hub import HubModelRecord, ModelSource


CURATED_MODELS: List[HubModelRecord] = [
    HubModelRecord(
        id="flux-1-schnell-fp8",
        name="FLUX.1 [schnell] (FP8 Quantized)",
        architecture="flux.1-schnell",
        category="checkpoint",
        version="1.0-fp8",
        size_bytes=11900000000,
        parameter_count="12B",
        quantization="FP8",
        author="Black Forest Labs",
        description="State-of-the-art fast open-weight image model. Exceptional prompt fidelity and photorealism in 4 steps.",
        preview_image_url="https://raw.githubusercontent.com/BerryUIKI/AI-Studio/main/frontend/public/assets/hub/flux_schnell.webp",
        tags=["photorealism", "text-rendering", "fast-inference"],
        recommended_resolution=[1024, 1024],
        min_vram_mb=8192,
        optimal_vram_mb=16384,
        sources=[
            ModelSource(
                name="HuggingFace (Direct)",
                url="https://huggingface.co/Comfy-Org/flux1-schnell/resolve/main/flux1-schnell-fp8.safetensors",
            ),
            ModelSource(
                name="HuggingFace (China Mirror)",
                url="https://hf-mirror.com/Comfy-Org/flux1-schnell/resolve/main/flux1-schnell-fp8.safetensors",
            ),
            ModelSource(
                name="ModelScope",
                url="https://www.modelscope.cn/models/AI-ModelScope/flux1-schnell-fp8/resolve/master/flux1-schnell-fp8.safetensors",
            ),
        ],
        sha256="4b6ca8189c441bbd5c5ff68f1262d08a0d4cbb8ad037b51b3fbcbeae6a20bc3a",
    ),
    HubModelRecord(
        id="sdxl-turbo-1.0",
        name="SDXL Turbo 1.0 (Real-Time)",
        architecture="sdxl",
        category="checkpoint",
        version="1.0",
        size_bytes=6900000000,
        parameter_count="3.5B",
        quantization="FP16",
        author="Stability AI",
        description="Adversarial Diffusion Distillation model capable of synthesized generation in a single inference step.",
        preview_image_url="https://raw.githubusercontent.com/BerryUIKI/AI-Studio/main/frontend/public/assets/hub/sdxl_turbo.webp",
        tags=["single-step", "real-time", "photorealism"],
        recommended_resolution=[1024, 1024],
        min_vram_mb=6144,
        optimal_vram_mb=10240,
        sources=[
            ModelSource(
                name="HuggingFace (Direct)",
                url="https://huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0_fp16.safetensors",
            ),
            ModelSource(
                name="HuggingFace (China Mirror)",
                url="https://hf-mirror.com/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0_fp16.safetensors",
            ),
        ],
        sha256="e8a443a5323e053a6154695015e1f0ba2b1f1f1a56667104b90150b4ec9d81d2",
    ),
    HubModelRecord(
        id="sd-1.5-v1-5-pruned",
        name="Stable Diffusion 1.5 Classic",
        architecture="sd-1.5",
        category="checkpoint",
        version="1.5",
        size_bytes=2130000000,
        parameter_count="1.5B",
        quantization="FP16",
        author="RunwayML",
        description="Lightweight standard diffusion foundation checkpoint with extensive ecosystem compatibility.",
        preview_image_url="https://raw.githubusercontent.com/BerryUIKI/AI-Studio/main/frontend/public/assets/hub/sd15.webp",
        tags=["classic", "low-vram", "universal"],
        recommended_resolution=[512, 512],
        min_vram_mb=4096,
        optimal_vram_mb=6144,
        sources=[
            ModelSource(
                name="HuggingFace (Direct)",
                url="https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors",
            ),
            ModelSource(
                name="HuggingFace (China Mirror)",
                url="https://hf-mirror.com/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors",
            ),
        ],
        sha256="6ce0161689b3853acaa03779e2088002771442a6644023695d664ffbd5b1a472",
    ),
    HubModelRecord(
        id="flux-1-dev-fp16",
        name="FLUX.1 [dev] Full Precision",
        architecture="flux.1-dev",
        category="checkpoint",
        version="1.0-fp16",
        size_bytes=23800000000,
        parameter_count="12B",
        quantization="FP16",
        author="Black Forest Labs",
        description="Full unquantized 12B guidance-distilled research checkpoint for premier quality and prompt alignment.",
        preview_image_url="https://raw.githubusercontent.com/BerryUIKI/AI-Studio/main/frontend/public/assets/hub/flux_dev.webp",
        tags=["highest-quality", "research", "studio-grade"],
        recommended_resolution=[1024, 1024],
        min_vram_mb=16384,
        optimal_vram_mb=24576,
        sources=[
            ModelSource(
                name="HuggingFace (Direct)",
                url="https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/flux1-dev.safetensors",
            ),
            ModelSource(
                name="HuggingFace (China Mirror)",
                url="https://hf-mirror.com/black-forest-labs/FLUX.1-dev/resolve/main/flux1-dev.safetensors",
            ),
        ],
        sha256="44bb978216c5cd41c2c8f8b377b219011986422bdf55f30740336ae9db607a2a",
    ),
    HubModelRecord(
        id="esrgan-4x-ultrasharp",
        name="4x-UltraSharp Upscaler",
        architecture="upscaler",
        category="upscaler",
        version="1.0",
        size_bytes=67000000,
        parameter_count="16M",
        quantization="FP32",
        author="Kim2091",
        description="Superior ESRGAN upscaling network delivering razor-sharp edge restoration without over-smoothing.",
        preview_image_url="https://raw.githubusercontent.com/BerryUIKI/AI-Studio/main/frontend/public/assets/hub/ultrasharp.webp",
        tags=["upscaling", "super-resolution", "sharpness"],
        recommended_resolution=[1024, 1024],
        min_vram_mb=2048,
        optimal_vram_mb=4096,
        sources=[
            ModelSource(
                name="HuggingFace (Direct)",
                url="https://huggingface.co/lokcx/4x-UltraSharp/resolve/main/4x-UltraSharp.pth",
            ),
            ModelSource(
                name="HuggingFace (China Mirror)",
                url="https://hf-mirror.com/lokcx/4x-UltraSharp/resolve/main/4x-UltraSharp.pth",
            ),
        ],
        sha256="599a0d2f0eb305c48b78912c3f87c2f6d0f171fd50e5fd556a3e5bf0d41df47a",
    ),
    HubModelRecord(
        id="real-esrgan-4x-plus",
        name="RealESRGAN_x4plus",
        architecture="upscaler",
        category="upscaler",
        version="0.2.5",
        size_bytes=67000000,
        parameter_count="16M",
        quantization="FP32",
        author="Xintao",
        description="Robust general-purpose natural photo upscaler trained on synthetic degradations.",
        preview_image_url="https://raw.githubusercontent.com/BerryUIKI/AI-Studio/main/frontend/public/assets/hub/realesrgan.webp",
        tags=["photo-enhancement", "artifact-removal"],
        recommended_resolution=[1024, 1024],
        min_vram_mb=2048,
        optimal_vram_mb=4096,
        sources=[
            ModelSource(
                name="HuggingFace (Direct)",
                url="https://huggingface.co/ai-forever/Real-ESRGAN/resolve/main/RealESRGAN_x4plus.pth",
            ),
        ],
        sha256="9924a515c0e157ab95e33d266e13ba97ff91e42714a8e32cbb41a027961b7b75",
    ),
    HubModelRecord(
        id="sdxl-lora-detail-tweaker",
        name="SDXL Detail Tweaker LoRA",
        architecture="sdxl",
        category="lora",
        version="1.0",
        size_bytes=140000000,
        parameter_count="8M",
        quantization="FP16",
        author="freepik",
        description="Fine detail intensity controller (+/- weight) for SDXL generations.",
        preview_image_url="https://raw.githubusercontent.com/BerryUIKI/AI-Studio/main/frontend/public/assets/hub/detail_lora.webp",
        tags=["detail-enhancer", "lora", "sdxl"],
        recommended_resolution=[1024, 1024],
        min_vram_mb=4096,
        optimal_vram_mb=8192,
        sources=[
            ModelSource(
                name="HuggingFace (Direct)",
                url="https://huggingface.co/nerijs/sdxl-detail-lora/resolve/main/sdxl_detail_lora.safetensors",
            ),
        ],
    ),
]


class HubCatalog:
    """Manages querying and filtering of the curated Model Hub catalog."""

    @classmethod
    def list_models(
        cls,
        category: Optional[str] = None,
        architecture: Optional[str] = None,
        query: Optional[str] = None,
    ) -> List[HubModelRecord]:
        results = list(CURATED_MODELS)

        if category and category.lower() != "all":
            results = [m for m in results if m.category.lower() == category.lower()]

        if architecture and architecture.lower() != "all":
            results = [m for m in results if architecture.lower() in m.architecture.lower()]

        if query and query.strip():
            q = query.strip().lower()
            results = [
                m
                for m in results
                if q in m.name.lower()
                or q in m.architecture.lower()
                or q in m.author.lower()
                or any(q in t.lower() for t in m.tags)
            ]

        return results

    @classmethod
    def get_model(cls, model_id: str) -> Optional[HubModelRecord]:
        return next((m for m in CURATED_MODELS if m.id == model_id), None)
