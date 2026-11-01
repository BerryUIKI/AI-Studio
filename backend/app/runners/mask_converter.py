"""Normalize inpainting masks without changing their dimensions or coordinates.

Berry uses alpha as edit coverage: painted/opaque = edit, transparent = protect.
ComfyUI LoadImage and OpenAI use inverse alpha. WebUI and the supported Fal
flux-general/inpainting endpoint use grayscale white = edit, black = protect.
"""

from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile

from PIL import Image, ImageOps


def _mask_image(mask_bytes: bytes, inverse_alpha: bool) -> bytes:
    """Encode edit coverage explicitly, preserving antialiased edges."""
    try:
        with Image.open(BytesIO(mask_bytes)) as source:
            if "A" not in source.getbands() and "transparency" not in source.info:
                raise ValueError("Berry masks must include an alpha channel")
            rgba = source.convert("RGBA")
            alpha = rgba.getchannel("A")
            if inverse_alpha:
                result = Image.new("RGBA", rgba.size, "white")
                result.putalpha(ImageOps.invert(alpha))
            else:
                result = alpha
            output = BytesIO()
            result.save(output, "PNG")
            return output.getvalue()
    except (OSError, ValueError) as error:
        raise ValueError(f"Invalid Berry mask: {error}") from error


def normalize_mask_for_comfyui(mask_path: Path) -> Path:
    """Create a unique PNG with inverted alpha for ComfyUI's 1-alpha mask."""
    if not mask_path.is_file():
        raise FileNotFoundError(f"Mask file not found: {mask_path}")
    converted = _mask_image(mask_path.read_bytes(), inverse_alpha=True)
    with NamedTemporaryFile(dir=mask_path.parent, prefix="berry-mask-", suffix=".png", delete=False) as output:
        output.write(converted)
        return Path(output.name)


def normalize_mask_for_webui(mask_bytes: bytes) -> bytes:
    """Encode alpha coverage as grayscale white=edit, black=protect."""
    return _mask_image(mask_bytes, inverse_alpha=False)


def normalize_mask_for_openai(mask_bytes: bytes) -> bytes:
    """Encode inverse alpha: transparent=edit, opaque=protect."""
    return _mask_image(mask_bytes, inverse_alpha=True)


def normalize_mask_for_fal_ai(mask_bytes: bytes) -> bytes:
    """Encode grayscale coverage for flux-general/inpainting."""
    return _mask_image(mask_bytes, inverse_alpha=False)


def validate_mask_dimensions(mask_path: Path, source_width: int, source_height: int) -> tuple[int, int]:
    """Reject mismatched masks instead of guessing how to resize coordinates."""
    with Image.open(mask_path) as mask:
        if mask.size != (source_width, source_height):
            raise ValueError(
                f"Mask dimensions ({mask.width}x{mask.height}) do not match "
                f"source dimensions ({source_width}x{source_height}). "
                "Source and mask must have identical dimensions for proper alignment."
            )
        return mask.size
