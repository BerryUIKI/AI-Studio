"""Unit tests for macro subgraph compiler and local ComfyUI node execution."""

import pytest
from app.main import app
from app.nodes.registry import registry
from app.runners.macro_compiler import build_comfy_txt2img_graph
from app.runners.comfy_runner import run_comfy_txt2img_node
from app.schemas.node import DataType


def test_macro_graph_structure():
    """Macro compiler outputs valid ComfyUI prompt dictionary with correct link slots."""
    graph = build_comfy_txt2img_graph(
        prompt="masterpiece, highly detailed cyberpunk street",
        negative_prompt="blurry, low quality",
        checkpoint="dreamshaper_8.safetensors",
        steps=25,
        cfg=7.5,
        aspect_ratio="16:9",
        seed=42,
    )

    # Core node existence
    assert "4" in graph  # CheckpointLoaderSimple
    assert "5" in graph  # EmptyLatentImage
    assert "6" in graph  # Positive CLIP
    assert "7" in graph  # Negative CLIP
    assert "3" in graph  # KSampler
    assert "8" in graph  # VAEDecode
    assert "9" in graph  # SaveImage

    # Aspect ratio mapping
    assert graph["5"]["inputs"]["width"] == 1344
    assert graph["5"]["inputs"]["height"] == 768

    # Parameters propagation
    assert graph["4"]["inputs"]["ckpt_name"] == "dreamshaper_8.safetensors"
    assert graph["3"]["inputs"]["steps"] == 25
    assert graph["3"]["inputs"]["cfg"] == 7.5
    assert graph["3"]["inputs"]["seed"] == 42
    assert graph["6"]["inputs"]["text"] == "masterpiece, highly detailed cyberpunk street"
    assert graph["7"]["inputs"]["text"] == "blurry, low quality"

    # Linkage integrity
    assert graph["3"]["inputs"]["positive"] == ["6", 0]
    assert graph["3"]["inputs"]["negative"] == ["7", 0]
    assert graph["3"]["inputs"]["latent_image"] == ["5", 0]
    assert graph["8"]["inputs"]["samples"] == ["3", 0]
    assert graph["8"]["inputs"]["vae"] == ["4", 2]
    assert graph["9"]["inputs"]["images"] == ["8", 0]


def test_macro_graph_with_lora_injection():
    """Injecting a LoRA creates Node 10 and re-routes Model and CLIP connections."""
    graph = build_comfy_txt2img_graph(
        prompt="portrait of a cyberpunk warrior",
        checkpoint="sd_xl_base_1.0.safetensors",
        lora_name="detail_tweaker.safetensors",
        lora_strength=0.8,
    )

    assert "10" in graph
    assert graph["10"]["class_type"] == "LoraLoader"
    assert graph["10"]["inputs"]["lora_name"] == "detail_tweaker.safetensors"
    assert graph["10"]["inputs"]["strength_model"] == 0.8

    # KSampler and CLIP should take model/clip from LoRA node 10, not directly from 4
    assert graph["3"]["inputs"]["model"] == ["10", 0]
    assert graph["6"]["inputs"]["clip"] == ["10", 1]


def test_builtin_comfy_node_registered():
    """image.comfy.txt2img is registered in the node library conforming to 5-type contract."""
    node_def = registry.get("image.comfy.txt2img")
    assert node_def is not None
    assert node_def.title == "Local ComfyUI Txt2Img"
    assert node_def.category.value == "image"

    # Verify input / output types
    input_types = [p.type.value for p in node_def.inputs]
    assert input_types == ["string", "string"]

    output_types = [p.type.value for p in node_def.outputs]
    assert output_types == ["image"]


@pytest.mark.asyncio
async def test_run_comfy_node_offline_error():
    """Executing ComfyUI node when offline yields NodeErrorEvent and error status."""
    events = []
    async for event in run_comfy_txt2img_node(
        node_id="test_node_1",
        inputs={"prompt": "beautiful mountain landscape"},
        params={"checkpoint": "v1-5.safetensors"},
    ):
        events.append(event)

    types = [e.type for e in events]
    assert "NODE_STATUS" in types
    assert "NODE_ERROR" in types

    # Last status should be error
    final_status = next(e for e in reversed(events) if e.type == "NODE_STATUS")
    assert final_status.status == "error"


def test_build_comfy_upscale_graph_native_4x_requested_at_2x():
    """When a native-4x model is requested at 2x, an ImageScale node rescales to exact 2x dimensions."""
    from app.runners.macro_compiler import build_comfy_upscale_graph

    # 640x360 landscape at 2x -> target 1280x720
    graph = build_comfy_upscale_graph(
        image_filename="fixture_640x360.png",
        upscaler_model="RealESRGAN_x4plus.pth",
        upscale_factor=2.0,
        source_width=640,
        source_height=360,
    )

    # Core nodes
    assert graph["1"]["class_type"] == "LoadImage"
    assert graph["2"]["class_type"] == "UpscaleModelLoader"
    assert graph["3"]["class_type"] == "ImageUpscaleWithModel"

    # Because model is 4x and request is 2x, ImageScale must be inserted
    assert "4" in graph
    assert graph["4"]["class_type"] == "ImageScale"
    assert graph["4"]["inputs"]["width"] == 1280
    assert graph["4"]["inputs"]["height"] == 720
    assert graph["4"]["inputs"]["upscale_method"] == "lanczos"
    assert graph["4"]["inputs"]["image"] == ["3", 0]

    # SaveImage must save from node 4
    assert graph["5"]["class_type"] == "SaveImage"
    assert graph["5"]["inputs"]["images"] == ["4", 0]


def test_build_comfy_upscale_graph_native_4x_requested_at_4x():
    """When a native-4x model is requested at 4x, SaveImage connects directly to model output."""
    from app.runners.macro_compiler import build_comfy_upscale_graph

    # 640x360 landscape at 4x -> target 2560x1440
    graph = build_comfy_upscale_graph(
        image_filename="fixture_640x360.png",
        upscaler_model="RealESRGAN_x4plus.pth",
        upscale_factor=4.0,
        source_width=640,
        source_height=360,
    )

    assert graph["3"]["class_type"] == "ImageUpscaleWithModel"
    # No extra ImageScale node needed
    assert "4" in graph
    assert graph["4"]["class_type"] == "SaveImage"
    assert graph["4"]["inputs"]["images"] == ["3", 0]


def test_build_comfy_upscale_graph_portrait():
    """Portrait inputs (e.g. 360x640) scale correctly without distortion."""
    from app.runners.macro_compiler import build_comfy_upscale_graph

    # 360x640 portrait at 2x -> target 720x1280
    graph = build_comfy_upscale_graph(
        image_filename="fixture_360x640.png",
        upscaler_model="RealESRGAN_x4plus.pth",
        upscale_factor=2.0,
        source_width=360,
        source_height=640,
    )

    assert graph["4"]["class_type"] == "ImageScale"
    assert graph["4"]["inputs"]["width"] == 720
    assert graph["4"]["inputs"]["height"] == 1280
    assert graph["5"]["inputs"]["images"] == ["4", 0]
