"""
Tests for mask conversion and normalization (Issue #106).

Verifies Berry mask convention (painted white = edit, transparent = protect)
is correctly converted for each provider's specific requirements.
"""

import pytest
import tempfile
from pathlib import Path
from PIL import Image

from app.runners.mask_converter import (
    normalize_mask_for_comfyui,
    normalize_mask_for_webui,
    normalize_mask_for_openai,
    normalize_mask_for_fal_ai,
    validate_mask_dimensions,
)


def create_test_mask(width: int, height: int, painted_region: tuple) -> bytes:
    """
    Create a Berry-convention test mask with a specific painted region.

    Args:
        width: Mask width
        height: Mask height
        painted_region: (x, y, w, h) rectangle to paint white

    Returns:
        PNG bytes with transparent background and white painted rectangle
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = img.load()

    x, y, w, h = painted_region
    for py in range(y, min(y + h, height)):
        for px in range(x, min(x + w, width)):
            pixels[px, py] = (255, 255, 255, 255)  # White opaque = edit region

    from io import BytesIO
    output = BytesIO()
    img.save(output, "PNG")
    return output.getvalue()


def test_berry_mask_convention_documented():
    """Verify the canonical Berry mask convention is clear."""
    # Berry convention: painted (white, alpha=255) = edit, transparent (alpha=0) = protect
    mask_bytes = create_test_mask(100, 100, (10, 10, 30, 30))
    img = Image.open(BytesIO(mask_bytes)).convert("RGBA")

    # Painted region should be opaque white
    assert img.getpixel((20, 20)) == (255, 255, 255, 255)

    # Unpainted region should be transparent
    assert img.getpixel((5, 5))[3] == 0


def test_comfyui_mask_inversion():
    """
    ComfyUI LoadImage MASK output = 1 - alpha.
    Painted regions (alpha=255) must become 0, transparent (alpha=0) must become 255.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        mask_path = Path(tmpdir) / "berry_mask.png"
        mask_bytes = create_test_mask(100, 100, (20, 20, 40, 40))
        mask_path.write_bytes(mask_bytes)

        converted_path = normalize_mask_for_comfyui(mask_path)

        try:
            converted = Image.open(converted_path).convert("RGBA")

            # Painted region in Berry (alpha=255) should become alpha=0 for ComfyUI
            painted_pixel = converted.getpixel((30, 30))
            assert painted_pixel[3] == 0, f"Painted region should have alpha=0, got {painted_pixel[3]}"

            # Unpainted region in Berry (alpha=0) should become alpha=255 for ComfyUI
            unpainted_pixel = converted.getpixel((5, 5))
            assert unpainted_pixel[3] == 255, f"Unpainted region should have alpha=255, got {unpainted_pixel[3]}"
        finally:
            if converted_path.exists():
                converted_path.unlink()


def test_webui_mask_grayscale_conversion():
    """
    WebUI expects grayscale where white=edit, black=protect.
    Berry convention already matches semantically, just convert format.
    """
    mask_bytes = create_test_mask(100, 100, (10, 10, 50, 50))
    converted_bytes = normalize_mask_for_webui(mask_bytes)

    converted = Image.open(BytesIO(converted_bytes))
    assert converted.mode == "L", "WebUI mask should be grayscale (mode L)"

    # Painted region should be white (255)
    assert converted.getpixel((30, 30)) == 255

    # Unpainted region should be black (0)
    assert converted.getpixel((5, 5)) == 0


def test_openai_mask_alpha_inversion():
    """
    OpenAI expects transparent (alpha=0) = edit, opaque (alpha=255) = protect.
    This is inverted from Berry convention.
    """
    mask_bytes = create_test_mask(100, 100, (15, 15, 30, 30))
    converted_bytes = normalize_mask_for_openai(mask_bytes)

    converted = Image.open(BytesIO(converted_bytes)).convert("RGBA")

    # Painted region in Berry (alpha=255) should become alpha=0 for OpenAI (edit)
    painted_pixel = converted.getpixel((25, 25))
    assert painted_pixel[3] == 0, f"Painted region should have alpha=0 for OpenAI, got {painted_pixel[3]}"

    # Unpainted region in Berry (alpha=0) should become alpha=255 for OpenAI (protect)
    unpainted_pixel = converted.getpixel((5, 5))
    assert unpainted_pixel[3] == 255, f"Unpainted region should have alpha=255 for OpenAI, got {unpainted_pixel[3]}"


def test_fal_ai_mask_passthrough():
    """
    Fal.ai expects opaque (alpha=255) = edit, transparent (alpha=0) = protect.
    This matches Berry convention exactly - just validate format.
    """
    mask_bytes = create_test_mask(100, 100, (20, 20, 40, 40))
    converted_bytes = normalize_mask_for_fal_ai(mask_bytes)

    # Should return original bytes since format matches
    converted = Image.open(BytesIO(converted_bytes)).convert("RGBA")

    # Painted region should still be opaque
    assert converted.getpixel((30, 30))[3] == 255

    # Unpainted region should still be transparent
    assert converted.getpixel((5, 5))[3] == 0


def test_mask_dimension_validation_success():
    """Validate that matching dimensions pass validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mask_path = Path(tmpdir) / "mask.png"
        mask_bytes = create_test_mask(512, 512, (100, 100, 200, 200))
        mask_path.write_bytes(mask_bytes)

        width, height = validate_mask_dimensions(mask_path, 512, 512)
        assert width == 512
        assert height == 512


def test_mask_dimension_validation_mismatch():
    """Validate that mismatched dimensions raise ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mask_path = Path(tmpdir) / "mask.png"
        mask_bytes = create_test_mask(512, 512, (100, 100, 200, 200))
        mask_path.write_bytes(mask_bytes)

        with pytest.raises(ValueError) as exc_info:
            validate_mask_dimensions(mask_path, 1024, 1024)

        assert "do not match" in str(exc_info.value).lower()
        assert "512" in str(exc_info.value)
        assert "1024" in str(exc_info.value)


def test_mask_dimension_validation_file_not_found():
    """Validate that missing mask file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        validate_mask_dimensions(Path("/nonexistent/mask.png"), 512, 512)


def test_comfyui_conversion_preserves_dimensions():
    """Verify ComfyUI conversion maintains exact dimensions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mask_path = Path(tmpdir) / "mask.png"
        mask_bytes = create_test_mask(768, 512, (50, 50, 100, 100))
        mask_path.write_bytes(mask_bytes)

        converted_path = normalize_mask_for_comfyui(mask_path)

        try:
            converted = Image.open(converted_path)
            assert converted.size == (768, 512)
            converted.close()
        finally:
            if converted_path.exists():
                try:
                    converted_path.unlink()
                except PermissionError:
                    pass  # Windows file lock issue in tests


def test_webui_conversion_preserves_dimensions():
    """Verify WebUI conversion maintains exact dimensions."""
    mask_bytes = create_test_mask(1024, 768, (100, 100, 200, 200))
    converted_bytes = normalize_mask_for_webui(mask_bytes)

    converted = Image.open(BytesIO(converted_bytes))
    assert converted.size == (1024, 768)


def test_partial_alpha_mask_conversion():
    """Test conversion with partial transparency (anti-aliased edges)."""
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    pixels = img.load()

    # Create gradient from transparent to opaque
    for x in range(50):
        alpha = int((x / 50.0) * 255)
        pixels[x, 50] = (255, 255, 255, alpha)

    from io import BytesIO
    mask_bytes = BytesIO()
    img.save(mask_bytes, "PNG")
    mask_bytes = mask_bytes.getvalue()

    # ComfyUI: should invert alpha gradient
    with tempfile.TemporaryDirectory() as tmpdir:
        mask_path = Path(tmpdir) / "mask.png"
        mask_path.write_bytes(mask_bytes)
        converted = normalize_mask_for_comfyui(mask_path)
        comfy_img = Image.open(converted).convert("RGBA")

        # Check gradient is inverted (approximately, allowing for conversion rounding)
        assert comfy_img.getpixel((0, 50))[3] == 255  # Was 0, should be 255
        assert comfy_img.getpixel((49, 50))[3] <= 10  # Was ~255, should be ~0 (allow small error)

        comfy_img.close()
        converted.unlink(missing_ok=True)


def test_fully_painted_mask():
    """Test mask that is completely painted (no transparent regions)."""
    img = Image.new("RGBA", (50, 50), (255, 255, 255, 255))

    from io import BytesIO
    mask_bytes = BytesIO()
    img.save(mask_bytes, "PNG")
    mask_bytes = mask_bytes.getvalue()

    # ComfyUI: all should become alpha=0
    with tempfile.TemporaryDirectory() as tmpdir:
        mask_path = Path(tmpdir) / "full_mask.png"
        mask_path.write_bytes(mask_bytes)
        converted = normalize_mask_for_comfyui(mask_path)
        comfy_img = Image.open(converted).convert("RGBA")
        converted.unlink()

    assert comfy_img.getpixel((25, 25))[3] == 0
    assert comfy_img.getpixel((0, 0))[3] == 0


def test_fully_transparent_mask():
    """Test mask that is completely transparent (no painted regions)."""
    img = Image.new("RGBA", (50, 50), (0, 0, 0, 0))

    from io import BytesIO
    mask_bytes = BytesIO()
    img.save(mask_bytes, "PNG")
    mask_bytes = mask_bytes.getvalue()

    # ComfyUI: all should become alpha=255
    with tempfile.TemporaryDirectory() as tmpdir:
        mask_path = Path(tmpdir) / "empty_mask.png"
        mask_path.write_bytes(mask_bytes)
        converted = normalize_mask_for_comfyui(mask_path)
        comfy_img = Image.open(converted).convert("RGBA")
        converted.unlink()

    assert comfy_img.getpixel((25, 25))[3] == 255
    assert comfy_img.getpixel((0, 0))[3] == 255


from io import BytesIO
