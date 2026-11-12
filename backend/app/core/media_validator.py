"""
Media validation and content isolation utilities for Berry AI Studio.

Ensures:
1. Strict size and decoded-pixel bounds on uploaded media.
2. Binary magic-byte format validation and normalization (PNG, JPEG, WebP, MP4, WebM).
3. Active/executable content (HTML, SVG, JS, PHP, EXE) rejection.
4. Safe Content-Security-Policy and header isolation when serving stored media.
"""

from pathlib import Path
import re
import struct
from typing import Dict, Optional, Tuple
from fastapi import HTTPException

# Maximum allowed file upload size: 50MB
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Maximum allowed pixel dimensions (8K)
MAX_IMAGE_DIM = 8192
MAX_TOTAL_PIXELS = 8192 * 8192

# Safe media content headers
MEDIA_SECURITY_HEADERS: Dict[str, str] = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


def sanitize_filename(filename: Optional[str], default_ext: str = ".png") -> str:
    """Sanitize filename to prevent directory traversal and illegal characters."""
    if not filename:
        return f"upload{default_ext}"
    base = Path(filename).name
    # Remove any characters outside alphanumeric, dash, underscore, and dot
    clean = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", base)
    if not clean or clean.startswith("."):
        return f"upload{default_ext}"
    return clean


def validate_and_inspect_media(
    data: bytes, filename: Optional[str] = None
) -> Tuple[str, int, int]:
    """
    Validate binary media payload against allowed types and bounds.
    Returns: (normalized_mime_type, width, height)
    """
    if not data:
        raise HTTPException(status_code=400, detail="Empty media payload")

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded file exceeds maximum limit of {MAX_UPLOAD_BYTES // (1024 * 1024)}MB",
        )

    # Reject active content signatures early
    lower_prefix = data[:1024].lower()
    if (
        b"<html" in lower_prefix
        or b"<!doctype html" in lower_prefix
        or b"<svg" in lower_prefix
        or b"<?xml" in lower_prefix
        or b"<script" in lower_prefix
        or b"<?php" in lower_prefix
    ):
        raise HTTPException(
            status_code=400,
            detail="Active or executable content (HTML, SVG, XML, scripts) is forbidden as creative assets.",
        )

    if len(data) < 8:
        raise HTTPException(status_code=400, detail="Malformed media header: file too small")

    # 1. PNG check
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        if len(data) < 24:
            raise HTTPException(status_code=400, detail="Malformed PNG: missing IHDR header")
        w, h = struct.unpack(">II", data[16:24])
        _validate_dimensions(w, h)
        return "image/png", w, h

    # 2. JPEG check
    if data.startswith(b"\xff\xd8\xff"):
        w, h = _parse_jpeg_dimensions(data)
        if w > 0 and h > 0:
            _validate_dimensions(w, h)
        return "image/jpeg", w, h

    # 3. WebP check (RIFF....WEBP)
    if data[:4] == b"RIFF" and len(data) >= 12 and data[8:12] == b"WEBP":
        w, h = _parse_webp_dimensions(data)
        if w > 0 and h > 0:
            _validate_dimensions(w, h)
        return "image/webp", w, h

    # 4. MP4 check (ftyp box at byte 4)
    if data.startswith((b"GIF87a", b"GIF89a")):
        if len(data) < 10:
            raise HTTPException(status_code=400, detail="Malformed GIF header")
        w, h = struct.unpack("<HH", data[6:10])
        _validate_dimensions(w, h)
        return "image/gif", w, h

    if len(data) >= 12 and data[4:8] in (b"ftyp", b"moov"):
        return "video/mp4", 0, 0

    # 5. WebM check (EBML header)
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm", 0, 0

    raise HTTPException(
        status_code=400,
        detail="Unsupported or unrecognized media format. Allowed formats: PNG, JPEG, WebP, GIF, MP4, WebM.",
    )


def inspect_media_metadata(data: bytes) -> Dict[str, object]:
    """Identify stored bytes; a file suffix or requested action never determines MIME."""
    mime, _, _ = validate_and_inspect_media(data)
    extensions = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
                  "image/gif": ".gif", "video/mp4": ".mp4", "video/webm": ".webm"}
    animated = False
    if mime.startswith("image/"):
        import io
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            animated = bool(getattr(image, "is_animated", False))
    return {"mime_type": mime, "extension": extensions[mime], "is_animated": animated,
            "codec": None}  # Container signatures do not prove a video codec.


def normalize_source_png(data: bytes) -> bytes:
    """Encode a decoded source frame as PNG for adapters whose input contract is PNG."""
    import io
    from PIL import Image
    mime, _, _ = validate_and_inspect_media(data)
    if not mime.startswith("image/"):
        raise ValueError("Cloud source must be an image")
    with Image.open(io.BytesIO(data)) as source:
        source.load()
        normalized = source.convert("RGBA" if "A" in source.getbands() or "transparency" in source.info else "RGB")
        try:
            output = io.BytesIO()
            normalized.save(output, format="PNG")
            return output.getvalue()
        finally:
            normalized.close()


def _validate_dimensions(w: int, h: int) -> None:
    if w <= 0 or h <= 0:
        raise HTTPException(status_code=400, detail="Invalid image dimensions (width and height must be positive)")
    if w > MAX_IMAGE_DIM or h > MAX_IMAGE_DIM:
        raise HTTPException(
            status_code=400,
            detail=f"Image dimensions ({w}x{h}) exceed maximum allowed dimension of {MAX_IMAGE_DIM}px",
        )
    if (w * h) > MAX_TOTAL_PIXELS:
        raise HTTPException(
            status_code=400,
            detail=f"Total pixel count ({w * h}) exceeds maximum allowed limit of {MAX_TOTAL_PIXELS}px",
        )


def _parse_jpeg_dimensions(data: bytes) -> Tuple[int, int]:
    """Parse JPEG SOF markers to extract width and height."""
    idx = 2
    length_data = len(data)
    while idx < length_data - 8:
        if data[idx] != 0xFF:
            idx += 1
            continue
        marker = data[idx + 1]
        # Baseline / Progressive SOF markers: 0xC0 .. 0xC3
        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            try:
                h, w = struct.unpack(">HH", data[idx + 5 : idx + 9])
                return w, h
            except Exception:
                return 0, 0
        try:
            seg_len = struct.unpack(">H", data[idx + 2 : idx + 4])[0]
            idx += 2 + seg_len
        except Exception:
            break
    return 0, 0


def _parse_webp_dimensions(data: bytes) -> Tuple[int, int]:
    """Parse WebP VP8/VP8L/VP8X chunk to extract dimensions."""
    try:
        chunk_type = data[12:16]
        if chunk_type == b"VP8 " and len(data) >= 30:
            # 24-bit width and height
            w = struct.unpack("<H", data[26:28])[0] & 0x3FFF
            h = struct.unpack("<H", data[28:30])[0] & 0x3FFF
            return w, h
        elif chunk_type == b"VP8L" and len(data) >= 25:
            b0, b1, b2, b3 = data[21:25]
            w = 1 + (((b1 & 0x3F) << 8) | b0)
            h = 1 + (((b3 & 0xF) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
            return w, h
        elif chunk_type == b"VP8X" and len(data) >= 30:
            w = 1 + (data[24] | (data[25] << 8) | (data[26] << 16))
            h = 1 + (data[27] | (data[28] << 8) | (data[29] << 16))
            return w, h
    except Exception:
        pass
    return 0, 0
