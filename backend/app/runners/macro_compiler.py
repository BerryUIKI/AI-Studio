"""
Macro Subgraph Compiler.

Translates high-level, human-friendly node parameters into ComfyUI's internal
low-level DAG (/prompt JSON specification), abstracting away latents, VAEs,
and conditioning linkages from the user.
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
    """
    Compile a high-level text-to-image request into a complete ComfyUI prompt graph.
    """
    width, height = ASPECT_RATIO_DIMENSIONS.get(aspect_ratio, (1024, 1024))
    actual_seed = seed if seed is not None else random.randint(1, 1125899906842624)

    graph: Dict[str, Any] = {}

    # Node 4: Load Checkpoint
    graph["4"] = {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": checkpoint,
        },
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
        "inputs": {
            "width": width,
            "height": height,
            "batch_size": 1,
        },
    }

    # Node 6: Positive Prompt CLIP Text Encode
    graph["6"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": prompt,
            "clip": clip_source,
        },
    }

    # Node 7: Negative Prompt CLIP Text Encode
    graph["7"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": negative_prompt,
            "clip": clip_source,
        },
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
        "inputs": {
            "samples": ["3", 0],
            "vae": ["4", 2],
        },
    }

    # Node 9: Save Image Output
    graph["9"] = {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": "AI-Workflow",
            "images": ["8", 0],
        },
    }

    return graph
