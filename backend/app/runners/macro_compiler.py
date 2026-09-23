"""
Macro Subgraph Compiler.

Translates high-level, human-friendly creative requests (txt2img, img2img, inpaint, upscale)
into ComfyUI's internal low-level DAG (/prompt JSON specification), abstracting away latents,
VAEs, and conditioning linkages from the user.
"""

import random
from typing import Any, Dict, Optional

# Standard aspect ratio mappings
ASPECT_RATIO_DIMENSIONS = {
    "1:1": (1024, 1024),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
    "4:3": (1152, 896),
    "3:4": (896, 1152),
}


def build_comfy_txt2img_graph(
    prompt: str,
    negative_prompt: str = "",
    checkpoint: str = "v1-5-pruned-emaonly.safetensors",
    steps: int = 20,
    cfg: float = 7.0,
    aspect_ratio: str = "1:1",
    seed: Optional[int] = None,
    sampler_name: str = "euler",
    scheduler: str = "normal",
    lora_name: Optional[str] = None,
    lora_strength: float = 1.0,
) -> Dict[str, Any]:
    """Compile a high-level text-to-image request into a complete ComfyUI prompt graph."""
    width, height = ASPECT_RATIO_DIMENSIONS.get(aspect_ratio, (1024, 1024))
    actual_seed = seed if seed is not None and seed >= 0 else random.randint(1, 1125899906842624)

    graph: Dict[str, Any] = {}

    # Node 4: Load Checkpoint
    graph["4"] = {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": checkpoint},
    }

    model_source = ["4", 0]
    clip_source = ["4", 1]

    # Optional Node 10: LoraLoader
    if lora_name:
        graph["10"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": model_source,
                "clip": clip_source,
                "lora_name": lora_name,
                "strength_model": lora_strength,
                "strength_clip": lora_strength,
            },
        }
        model_source = ["10", 0]
        clip_source = ["10", 1]

    # Node 5: Empty Latent Image
    graph["5"] = {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": width, "height": height, "batch_size": 1},
    }

    # Node 6: Positive Prompt CLIP Text Encode
    graph["6"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": prompt, "clip": clip_source},
    }

    # Node 7: Negative Prompt CLIP Text Encode
    graph["7"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": negative_prompt, "clip": clip_source},
    }

    # Node 3: KSampler
    graph["3"] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": actual_seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler_name,
            "scheduler": scheduler,
            "denoise": 1.0,
            "model": model_source,
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
        },
    }

    # Node 8: VAE Decode
    graph["8"] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
    }

    # Node 9: Save Image Output
    graph["9"] = {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "Berry-Txt2Img", "images": ["8", 0]},
    }

    return graph


def build_comfy_img2img_graph(
    prompt: str,
    image_filename: str,
    negative_prompt: str = "",
    checkpoint: str = "v1-5-pruned-emaonly.safetensors",
    steps: int = 20,
    cfg: float = 7.0,
    denoise: float = 0.75,
    seed: Optional[int] = None,
    sampler_name: str = "euler",
    scheduler: str = "normal",
) -> Dict[str, Any]:
    """Compile an image-to-image request into a complete ComfyUI prompt graph."""
    actual_seed = seed if seed is not None and seed >= 0 else random.randint(1, 1125899906842624)

    graph: Dict[str, Any] = {}

    graph["4"] = {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": checkpoint},
    }

    graph["1"] = {
        "class_type": "LoadImage",
        "inputs": {"image": image_filename},
    }

    graph["2"] = {
        "class_type": "VAEEncode",
        "inputs": {"pixels": ["1", 0], "vae": ["4", 2]},
    }

    graph["6"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": prompt, "clip": ["4", 1]},
    }

    graph["7"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": negative_prompt, "clip": ["4", 1]},
    }

    graph["3"] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": actual_seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler_name,
            "scheduler": scheduler,
            "denoise": denoise,
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["2", 0],
        },
    }

    graph["8"] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
    }

    graph["9"] = {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "Berry-Img2Img", "images": ["8", 0]},
    }

    return graph


def build_comfy_inpaint_graph(
    prompt: str,
    image_filename: str,
    mask_filename: str,
    negative_prompt: str = "",
    checkpoint: str = "v1-5-pruned-emaonly.safetensors",
    steps: int = 20,
    cfg: float = 7.0,
    denoise: float = 0.85,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Compile an inpainting request into a complete ComfyUI prompt graph."""
    actual_seed = seed if seed is not None and seed >= 0 else random.randint(1, 1125899906842624)

    graph: Dict[str, Any] = {}

    graph["4"] = {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": checkpoint},
    }

    graph["1"] = {
        "class_type": "LoadImage",
        "inputs": {"image": image_filename},
    }

    graph["2"] = {
        "class_type": "LoadImage",
        "inputs": {"image": mask_filename},
    }

    graph["5"] = {
        "class_type": "VAEEncodeForInpaint",
        "inputs": {
            "pixels": ["1", 0],
            "mask": ["2", 1],  # mask channel
            "vae": ["4", 2],
            "grow_mask_by": 6,
        },
    }

    graph["6"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": prompt, "clip": ["4", 1]},
    }

    graph["7"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": negative_prompt, "clip": ["4", 1]},
    }

    graph["3"] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": actual_seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": denoise,
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
        },
    }

    graph["8"] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
    }

    graph["9"] = {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "Berry-Inpaint", "images": ["8", 0]},
    }

    return graph


def build_comfy_upscale_graph(
    image_filename: str,
    upscaler_model: str = "RealESRGAN_x4plus.pth",
) -> Dict[str, Any]:
    """Compile an upscaling request into a ComfyUI prompt graph."""
    graph: Dict[str, Any] = {}

    graph["1"] = {
        "class_type": "LoadImage",
        "inputs": {"image": image_filename},
    }

    graph["2"] = {
        "class_type": "UpscaleModelLoader",
        "inputs": {"model_name": upscaler_model},
    }

    graph["3"] = {
        "class_type": "ImageUpscaleWithModel",
        "inputs": {
            "upscale_model": ["2", 0],
            "image": ["1", 0],
        },
    }

    graph["4"] = {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "Berry-Upscale", "images": ["3", 0]},
    }

    return graph


def build_comfy_img2video_graph(
    image_filename: str,
    checkpoint: str = "svd_xt.safetensors",
    width: int = 1024,
    height: int = 576,
    video_frames: int = 25,
    fps: int = 16,
    motion_bucket_id: int = 127,
    seed: Optional[int] = None,
    steps: int = 20,
    cfg: float = 2.5,
) -> Dict[str, Any]:
    """Compile an image-to-video request using SVD into a ComfyUI prompt graph."""
    actual_seed = seed if seed is not None and seed >= 0 else random.randint(1, 1125899906842624)
    graph: Dict[str, Any] = {}

    # Node 1: SVD Checkpoint Loader
    graph["1"] = {
        "class_type": "ImageOnlyCheckpointLoader",
        "inputs": {"ckpt_name": checkpoint},
    }

    # Node 2: Input Image
    graph["2"] = {
        "class_type": "LoadImage",
        "inputs": {"image": image_filename},
    }

    # Node 3: SVD Conditioning
    graph["3"] = {
        "class_type": "SVD_img2vid_Conditioning",
        "inputs": {
            "clip_vision": ["1", 1],
            "init_image": ["2", 0],
            "vae": ["1", 2],
            "width": width,
            "height": height,
            "video_frames": video_frames,
            "motion_bucket_id": motion_bucket_id,
            "fps": fps,
            "augmentation_level": 0.0,
        },
    }

    # Node 4: KSampler
    graph["4"] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": actual_seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": "euler",
            "scheduler": "karras",
            "denoise": 1.0,
            "model": ["1", 0],
            "positive": ["3", 0],
            "negative": ["3", 1],
            "latent_image": ["3", 2],
        },
    }

    # Node 5: VAEDecode
    graph["5"] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["4", 0], "vae": ["1", 2]},
    }

    # Node 6: Save Animated Output
    graph["6"] = {
        "class_type": "SaveAnimatedWEBP",
        "inputs": {
            "filename_prefix": "Berry-Img2Vid",
            "images": ["5", 0],
            "fps": fps,
            "lossless": False,
            "quality": 85,
            "method": "default",
        },
    }

    return graph


def build_comfy_txt2video_graph(
    prompt: str,
    negative_prompt: str = "",
    checkpoint: str = "v1-5-pruned-emaonly.safetensors",
    animatediff_model: str = "mm_sd_v15_v2.ckpt",
    width: int = 512,
    height: int = 512,
    video_frames: int = 16,
    fps: int = 8,
    seed: Optional[int] = None,
    steps: int = 20,
    cfg: float = 7.0,
) -> Dict[str, Any]:
    """Compile a text-to-video request using AnimateDiff into a ComfyUI prompt graph."""
    actual_seed = seed if seed is not None and seed >= 0 else random.randint(1, 1125899906842624)
    graph: Dict[str, Any] = {}

    # Node 1: Checkpoint Loader
    graph["1"] = {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": checkpoint},
    }

    # Node 2: AnimateDiff Loader
    graph["2"] = {
        "class_type": "AnimateDiffLoaderWithContext",
        "inputs": {
            "model": ["1", 0],
            "model_name": animatediff_model,
            "context_length": 16,
        },
    }

    # Node 3: Positive CLIP
    graph["3"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": prompt, "clip": ["1", 1]},
    }

    # Node 4: Negative CLIP
    graph["4"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": negative_prompt, "clip": ["1", 1]},
    }

    # Node 5: Empty Latent
    graph["5"] = {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": width, "height": height, "batch_size": video_frames},
    }

    # Node 6: KSampler
    graph["6"] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": actual_seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["2", 0],
            "positive": ["3", 0],
            "negative": ["4", 0],
            "latent_image": ["5", 0],
        },
    }

    # Node 7: VAEDecode
    graph["7"] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["6", 0], "vae": ["1", 2]},
    }

    # Node 8: Save Animated Output
    graph["8"] = {
        "class_type": "SaveAnimatedWEBP",
        "inputs": {
            "filename_prefix": "Berry-Txt2Vid",
            "images": ["7", 0],
            "fps": fps,
            "lossless": False,
            "quality": 85,
            "method": "default",
        },
    }

    return graph

