"""
Mask Conversion and Normalization for Inpainting (Issue #106).

Canonical Berry Mask Convention:
- Painted (opaque white, alpha=255) regions indicate areas TO BE EDITED by AI
- Unpainted (transparent, alpha=0) regions indicate areas TO BE PROTECTED (kept unchanged)

This module converts Berry masks to provider-specific formats:
- ComfyUI: LoadImage MASK output computes 1-alpha, requiring inversion
- WebUI: Expects grayscale where white=edit, black=protect (matches Berry)
- OpenAI: Uses alpha channel where transparent=edit (inverted from Berry)
- Fal.ai: Uses alpha channel where opaque=edit (matches Berry)

All conversions preserve source/mask dimensions and coordinate alignment.
"""

from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image


def normalize_mask_for_comfyui(mask_path: Path) -> Path:
    """
    Convert Berry mask to ComfyUI-compatible format.

    ComfyUI's LoadImage MASK output = 1 - alpha, so painted regions (alpha=255)
    become 0 (protect) instead of 1 (edit). We must invert the alpha channel.

    Args:
        mask_path: Path to Berry mask (white painted = edit, transparent = protect)

    Returns:
        Path to converted mask suitable for ComfyUI LoadImage MASK channel

    Raises:
        FileNotFoundError: If mask_path doesn't exist
        ValueError: If image cannot be processed
    """
    if not mask_path.is_file():
        raise FileNotFoundError(f"Mask file not found: {mask_path}")

    try:
        img = Image.open(mask_path).convert("RGBA")
        width, height = img.size
        pixels = img.load()

        # Invert alpha channel: painted (255) -> 0, transparent (0) -> 255
        for y in range(height):
            for x in range(width):
                r, g, b, a = pixels[x, y]
                pixels[x, y] = (255, 255, 255, 255 - a)

        # Save as temporary converted mask
        converted_path = mask_path.with_name(f"{mask_path.stem}_comfy{mask_path.suffix}")
        img.save(converted_path, "PNG")
        return converted_path

    except Exception as e:
        raise ValueError(f"Failed to convert mask for ComfyUI: {e}") from e


def normalize_mask_for_webui(mask_bytes: bytes) -> bytes:
    """
    Convert Berry mask to WebUI-compatible grayscale format.

    WebUI expects grayscale where:
    - White (255) = edit region
    - Black (0) = protect region

    Berry convention already matches this (painted white = edit), so we just
    convert alpha to grayscale: alpha channel -> single grayscale channel.

    Args:
        mask_bytes: Berry mask PNG bytes

    Returns:
        Converted grayscale mask PNG bytes

    Raises:
        ValueError: If image cannot be processed
    """
    try:
        img = Image.open(BytesIO(mask_bytes)).convert("RGBA")
        width, height = img.size

        # Create grayscale image where painted regions are white
        grayscale = Image.new("L", (width, height), 0)
        pixels_src = img.load()
        pixels_dst = grayscale.load()

        for y in range(height):
            for x in range(width):
                _, _, _, a = pixels_src[x, y]
                # Alpha 255 (painted) -> white 255 (edit)
                # Alpha 0 (transparent) -> black 0 (protect)
                pixels_dst[x, y] = a

        output = BytesIO()
        grayscale.save(output, "PNG")
        return output.getvalue()

    except Exception as e:
        raise ValueError(f"Failed to convert mask for WebUI: {e}") from e


def normalize_mask_for_openai(mask_bytes: bytes) -> bytes:
    """
    Convert Berry mask to OpenAI-compatible format.

    OpenAI expects alpha channel where:
    - Transparent (alpha=0) = edit region
    - Opaque (alpha=255) = protect region

    This is inverted from Berry convention, so we invert the alpha channel.

    Args:
        mask_bytes: Berry mask PNG bytes

    Returns:
        Converted mask PNG bytes with inverted alpha

    Raises:
        ValueError: If image cannot be processed
    """
    try:
        img = Image.open(BytesIO(mask_bytes)).convert("RGBA")
        width, height = img.size
        pixels = img.load()

        # Invert alpha: painted (255) -> 0 (edit), transparent (0) -> 255 (protect)
        for y in range(height):
            for x in range(width):
                r, g, b, a = pixels[x, y]
                pixels[x, y] = (r, g, b, 255 - a)

        output = BytesIO()
        img.save(output, "PNG")
        return output.getvalue()

    except Exception as e:
        raise ValueError(f"Failed to convert mask for OpenAI: {e}") from e


def normalize_mask_for_fal_ai(mask_bytes: bytes) -> bytes:
    """
    Convert Berry mask to Fal.ai-compatible format.

    Fal.ai expects alpha channel where:
    - Opaque (alpha=255) = edit region
    - Transparent (alpha=0) = protect region

    This matches Berry convention, so no conversion needed - just validate format.

    Args:
        mask_bytes: Berry mask PNG bytes

    Returns:
        Original mask bytes (already in correct format)

    Raises:
        ValueError: If image cannot be processed
    """
    try:
        # Validate image can be loaded
        img = Image.open(BytesIO(mask_bytes))
        img.verify()
        return mask_bytes

    except Exception as e:
        raise ValueError(f"Failed to validate mask for Fal.ai: {e}") from e


def validate_mask_dimensions(mask_path: Path, source_width: int, source_height: int) -> Tuple[int, int]:
    """
    Validate mask dimensions match source image dimensions.

    Args:
        mask_path: Path to mask image
        source_width: Expected width from source image
        source_height: Expected height from source image

    Returns:
        Tuple of (mask_width, mask_height)

    Raises:
        FileNotFoundError: If mask doesn't exist
        ValueError: If dimensions don't match
    """
    if not mask_path.is_file():
        raise FileNotFoundError(f"Mask file not found: {mask_path}")

    try:
        with Image.open(mask_path) as img:
            mask_width, mask_height = img.size

            if mask_width != source_width or mask_height != source_height:
                raise ValueError(
                    f"Mask dimensions ({mask_width}x{mask_height}) do not match "
                    f"source dimensions ({source_width}x{source_height}). "
                    "Source and mask must have identical dimensions for proper alignment."
                )

            return mask_width, mask_height

    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to validate mask dimensions: {e}") from e
