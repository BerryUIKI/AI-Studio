"""
Bounded Supported ComfyUI Workflow Catalog and Reviewable Graph Builder.

Provides a strictly bounded set of supported ComfyUI DAG workflows, required
node classes, required model dependencies, and transparent reviewable stage descriptions.
Enforces validation before execution and prevents raw ComfyUI ports/tensors from leaking
onto the primary creative canvas.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from app.runners.macro_compiler import (
    build_comfy_img2img_graph,
    build_comfy_img2video_graph,
    build_comfy_inpaint_graph,
    build_comfy_txt2img_graph,
    build_comfy_txt2video_graph,
    build_comfy_upscale_graph,
)
from app.core.workflow_validator import WorkflowValidator
from app.schemas.agent import ReviewableWorkflowGraph, WorkflowNodeStage


@dataclass
class WorkflowDefinition:
    workflow_id: str
    title: str
    category: str  # image, video, upscale
    description: str
    required_nodes: List[str]
    required_models: List[str]
    stages: List[WorkflowNodeStage]
    compiler: Callable[..., Dict[str, Any]]


BOUNDED_WORKFLOWS: Dict[str, WorkflowDefinition] = {
    "comfy.txt2img.standard": WorkflowDefinition(
        workflow_id="comfy.txt2img.standard",
        title="Standard Text-to-Image DAG",
        category="image",
        description="Standard latent diffusion generation from text prompt using checkpoint and CLIP.",
        required_nodes=[
            "CheckpointLoaderSimple",
            "EmptyLatentImage",
            "CLIPTextEncode",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        ],
        required_models=["checkpoint"],
        stages=[
            WorkflowNodeStage(stage_number=1, name="Model Loader", node_type="CheckpointLoaderSimple", description="Load model weights and CLIP/VAE tokenizers"),
            WorkflowNodeStage(stage_number=2, name="Prompt Encoding", node_type="CLIPTextEncode", description="Encode positive and negative text prompts into conditioning vectors"),
            WorkflowNodeStage(stage_number=3, name="Latent Space Initialization", node_type="EmptyLatentImage", description="Create empty latent tensor with requested aspect ratio"),
            WorkflowNodeStage(stage_number=4, name="Diffusion Sampling", node_type="KSampler", description="Iterative noise reduction with Euler/Karras scheduler"),
            WorkflowNodeStage(stage_number=5, name="Image Reconstruction", node_type="VAEDecode", description="Decode latent samples into final RGB pixel image"),
            WorkflowNodeStage(stage_number=6, name="Asset Storage", node_type="SaveImage", description="Persist generated asset with provenance metadata"),
        ],
        compiler=lambda **kwargs: build_comfy_txt2img_graph(
            prompt=kwargs.get("prompt", ""),
            negative_prompt=kwargs.get("negative_prompt", ""),
            checkpoint=kwargs.get("checkpoint", "v1-5-pruned-emaonly.safetensors"),
            steps=kwargs.get("steps", 20),
            cfg=kwargs.get("cfg", 7.0),
            aspect_ratio=kwargs.get("aspect_ratio", "1:1"),
            seed=kwargs.get("seed"),
        ),
    ),
    "comfy.img2img.standard": WorkflowDefinition(
        workflow_id="comfy.img2img.standard",
        title="Image-to-Image Variation DAG",
        category="image",
        description="Image-guided generation using source image latent encoding with adjustable denoise strength.",
        required_nodes=[
            "CheckpointLoaderSimple",
            "LoadImage",
            "VAEEncode",
            "CLIPTextEncode",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        ],
        required_models=["checkpoint"],
        stages=[
            WorkflowNodeStage(stage_number=1, name="Source Ingestion", node_type="LoadImage", description="Ingest input reference image from asset store"),
            WorkflowNodeStage(stage_number=2, name="Latent Encoding", node_type="VAEEncode", description="Compress input RGB image into latent representation"),
            WorkflowNodeStage(stage_number=3, name="Conditioning Encoding", node_type="CLIPTextEncode", description="Encode text guide prompts via CLIP"),
            WorkflowNodeStage(stage_number=4, name="Guided Resampling", node_type="KSampler", description="Denoise latent image towards prompt target"),
            WorkflowNodeStage(stage_number=5, name="Image Reconstruction", node_type="VAEDecode", description="Decode final latents to RGB image"),
            WorkflowNodeStage(stage_number=6, name="Asset Storage", node_type="SaveImage", description="Save modified asset"),
        ],
        compiler=lambda **kwargs: build_comfy_img2img_graph(
            image_filename=kwargs.get("image_filename", "input.png"),
            prompt=kwargs.get("prompt", ""),
            negative_prompt=kwargs.get("negative_prompt", ""),
            checkpoint=kwargs.get("checkpoint", "v1-5-pruned-emaonly.safetensors"),
            denoise=kwargs.get("denoise", 0.75),
            steps=kwargs.get("steps", 20),
            cfg=kwargs.get("cfg", 7.0),
            seed=kwargs.get("seed"),
        ),
    ),
    "comfy.inpaint.standard": WorkflowDefinition(
        workflow_id="comfy.inpaint.standard",
        title="Inpainting & Mask Replacement DAG",
        category="image",
        description="Localized image inpainting using source image and binary mask.",
        required_nodes=[
            "CheckpointLoaderSimple",
            "LoadImage",
            "VAEEncodeForInpaint",
            "CLIPTextEncode",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        ],
        required_models=["checkpoint"],
        stages=[
            WorkflowNodeStage(stage_number=1, name="Image & Mask Loading", node_type="LoadImage", description="Load source image and alpha mask"),
            WorkflowNodeStage(stage_number=2, name="Inpaint Encoding", node_type="VAEEncodeForInpaint", description="Prepare inpainting masked latents"),
            WorkflowNodeStage(stage_number=3, name="Prompt Encoding", node_type="CLIPTextEncode", description="Encode replacement prompt"),
            WorkflowNodeStage(stage_number=4, name="Masked Diffusion", node_type="KSampler", description="Synthesize new content inside masked region"),
            WorkflowNodeStage(stage_number=5, name="Seamless Decode", node_type="VAEDecode", description="Reconstruct blended RGB image"),
            WorkflowNodeStage(stage_number=6, name="Asset Storage", node_type="SaveImage", description="Save inpainted asset"),
        ],
        compiler=lambda **kwargs: build_comfy_inpaint_graph(
            image_filename=kwargs.get("image_filename", "input.png"),
            mask_filename=kwargs.get("mask_filename", "mask.png"),
            prompt=kwargs.get("prompt", ""),
            negative_prompt=kwargs.get("negative_prompt", ""),
            checkpoint=kwargs.get("checkpoint", "v1-5-pruned-emaonly.safetensors"),
            denoise=kwargs.get("denoise", 0.85),
            steps=kwargs.get("steps", 20),
            cfg=kwargs.get("cfg", 7.5),
            seed=kwargs.get("seed"),
        ),
    ),
    "comfy.upscale.esrgan": WorkflowDefinition(
        workflow_id="comfy.upscale.esrgan",
        title="Neural Super-Resolution Upscaling DAG",
        category="upscale",
        description="High-fidelity 4x image upscaling using neural RealESRGAN models.",
        required_nodes=[
            "LoadImage",
            "UpscaleModelLoader",
            "ImageUpscaleWithModel",
            "SaveImage",
        ],
        required_models=["RealESRGAN_x4plus.pth"],
        stages=[
            WorkflowNodeStage(stage_number=1, name="Image Ingestion", node_type="LoadImage", description="Load image to upscale"),
            WorkflowNodeStage(stage_number=2, name="Upscale Model Loader", node_type="UpscaleModelLoader", description="Load RealESRGAN neural model weights"),
            WorkflowNodeStage(stage_number=3, name="Neural Upscaling", node_type="ImageUpscaleWithModel", description="Apply super-resolution inference"),
            WorkflowNodeStage(stage_number=4, name="Asset Storage", node_type="SaveImage", description="Save high-resolution output asset"),
        ],
        compiler=lambda **kwargs: build_comfy_upscale_graph(
            image_filename=kwargs.get("image_filename", "input.png"),
            upscaler_model=kwargs.get("upscaler_model", "RealESRGAN_x4plus.pth"),
        ),
    ),
    "comfy.img2video.svd": WorkflowDefinition(
        workflow_id="comfy.img2video.svd",
        title="Stable Video Diffusion (SVD) Image-to-Video DAG",
        category="video",
        description="Synthesizes smooth video motion from a source image using Stable Video Diffusion.",
        required_nodes=[
            "ImageOnlyCheckpointLoader",
            "LoadImage",
            "SVD_img2vid_Conditioning",
            "KSampler",
            "VAEDecode",
            "SaveAnimatedWEBP",
        ],
        required_models=["svd_xt.safetensors"],
        stages=[
            WorkflowNodeStage(stage_number=1, name="SVD Model Loader", node_type="ImageOnlyCheckpointLoader", description="Load Stable Video Diffusion checkpoint"),
            WorkflowNodeStage(stage_number=2, name="Source Ingestion", node_type="LoadImage", description="Load starting frame image"),
            WorkflowNodeStage(stage_number=3, name="Motion Conditioning", node_type="SVD_img2vid_Conditioning", description="Calculate motion bucket, fps, and frame dimensions"),
            WorkflowNodeStage(stage_number=4, name="Temporal Sampling", node_type="KSampler", description="Sample multi-frame video latents"),
            WorkflowNodeStage(stage_number=5, name="Video Frame Decode", node_type="VAEDecode", description="Decode video frames from latent tensor"),
            WorkflowNodeStage(stage_number=6, name="Animated Storage", node_type="SaveAnimatedWEBP", description="Save animated WebP video output"),
        ],
        compiler=lambda **kwargs: build_comfy_img2video_graph(
            image_filename=kwargs.get("image_filename", "input.png"),
            checkpoint=kwargs.get("checkpoint", "svd_xt.safetensors"),
            width=kwargs.get("width", 1024),
            height=kwargs.get("height", 576),
            video_frames=kwargs.get("video_frames", 25),
            fps=kwargs.get("fps", 16),
            motion_bucket_id=kwargs.get("motion_bucket_id", 127),
            seed=kwargs.get("seed"),
        ),
    ),
    "comfy.txt2video.animatediff": WorkflowDefinition(
        workflow_id="comfy.txt2video.animatediff",
        title="AnimateDiff Text-to-Video DAG",
        category="video",
        description="Generates short animated video sequences from text prompts using SD1.5 and AnimateDiff motion modules.",
        required_nodes=[
            "CheckpointLoaderSimple",
            "AnimateDiffLoaderWithContext",
            "EmptyLatentImage",
            "CLIPTextEncode",
            "KSampler",
            "VAEDecode",
            "SaveAnimatedWEBP",
        ],
        required_models=["v1-5-pruned-emaonly.safetensors", "mm_sd_v15_v2.ckpt"],
        stages=[
            WorkflowNodeStage(stage_number=1, name="Base Checkpoint Loader", node_type="CheckpointLoaderSimple", description="Load base Stable Diffusion 1.5 weights"),
            WorkflowNodeStage(stage_number=2, name="Motion Module Loader", node_type="AnimateDiffLoaderWithContext", description="Inject temporal attention motion module"),
            WorkflowNodeStage(stage_number=3, name="Prompt Encoding", node_type="CLIPTextEncode", description="Encode text animation prompt"),
            WorkflowNodeStage(stage_number=4, name="Temporal Latent Sampling", node_type="KSampler", description="Sample animated motion latents"),
            WorkflowNodeStage(stage_number=5, name="Frame Decode", node_type="VAEDecode", description="Decode animated frames"),
            WorkflowNodeStage(stage_number=6, name="Save Animated Output", node_type="SaveAnimatedWEBP", description="Save animated WebP clip"),
        ],
        compiler=lambda **kwargs: build_comfy_txt2video_graph(
            prompt=kwargs.get("prompt", ""),
            negative_prompt=kwargs.get("negative_prompt", ""),
            checkpoint=kwargs.get("checkpoint", "v1-5-pruned-emaonly.safetensors"),
            animatediff_model=kwargs.get("animatediff_model", "mm_sd_v15_v2.ckpt"),
            width=kwargs.get("width", 512),
            height=kwargs.get("height", 512),
            video_frames=kwargs.get("video_frames", 16),
            fps=kwargs.get("fps", 8),
            seed=kwargs.get("seed"),
        ),
    ),
}


class WorkflowCatalog:
    """Registry and reviewable graph builder for bounded ComfyUI workflows."""

    @classmethod
    def list_workflows(cls) -> List[Dict[str, Any]]:
        """Return descriptions of all bounded supported workflows."""
        return [
            {
                "workflow_id": w.workflow_id,
                "title": w.title,
                "category": w.category,
                "description": w.description,
                "required_nodes": w.required_nodes,
                "required_models": w.required_models,
            }
            for w in BOUNDED_WORKFLOWS.values()
        ]

    @classmethod
    def get_workflow(cls, workflow_id: str) -> Optional[WorkflowDefinition]:
        return BOUNDED_WORKFLOWS.get(workflow_id)

    @classmethod
    def construct_workflow(
        cls,
        workflow_id: str,
        parameters: Dict[str, Any],
        model_catalog=None,
    ) -> tuple[Dict[str, Any], ReviewableWorkflowGraph]:
        """
        Construct a bounded ComfyUI prompt graph, validate it, and generate a reviewable summary.
        Does NOT execute or leak raw ports to the canvas.
        """
        defn = cls.get_workflow(workflow_id)
        if not defn:
            raise ValueError(f"Unknown bounded workflow: '{workflow_id}'")

        # Compile graph
        graph = defn.compiler(**parameters)

        # Validate graph
        validator = WorkflowValidator(model_catalog=model_catalog)
        val_report = validator.validate(graph)

        # Check required models
        missing_models: List[str] = list(val_report.missing_models)
        indexed_names = []
        if model_catalog:
            try:
                indexed_names = [m.name for m in model_catalog.get_models()]
            except Exception:
                pass

        for req_m in defn.required_models:
            if req_m not in ("checkpoint", "lora"):
                if indexed_names and req_m not in indexed_names and req_m not in missing_models:
                    missing_models.append(req_m)

        validation_issues = [f"[{i.severity.upper()}] {i.message}" for i in val_report.issues if i.severity == "error"]

        recovery_guidance = None
        if missing_models:
            recovery_guidance = (
                f"Missing required model(s): {', '.join(missing_models)}. "
                "Download them into your engine models directory or switch to Cloud BYOK in Cloud Settings."
            )
        elif not val_report.valid:
            recovery_guidance = "Workflow graph has structural validation errors. Check node connections or use Workflow Repair."

        reviewable = ReviewableWorkflowGraph(
            workflow_id=defn.workflow_id,
            workflow_title=defn.title,
            node_count=len(graph),
            stages=defn.stages,
            required_nodes=defn.required_nodes,
            required_models=defn.required_models,
            missing_models=missing_models,
            is_valid=val_report.valid and len(missing_models) == 0,
            validation_issues=validation_issues,
            recovery_guidance=recovery_guidance,
        )

        return graph, reviewable
