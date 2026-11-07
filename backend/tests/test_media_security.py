import io
import struct
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.media_validator import (
    sanitize_filename,
    validate_and_inspect_media,
    MAX_UPLOAD_BYTES,
    MAX_IMAGE_DIM,
)

client = TestClient(app)

TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x20\x00\x00\x00\x10"
    b"\x08\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0aIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_sanitize_filename():
    assert sanitize_filename("../../secret.png") == "secret.png"
    assert sanitize_filename("..\\..\\windows.png") == "windows.png"
    assert sanitize_filename("normal_image.jpg") == "normal_image.jpg"
    assert sanitize_filename(".hidden") == "upload.png"
    assert sanitize_filename("") == "upload.png"


def test_valid_png_upload():
    response = client.post(
        "/api/v1/creative/upload",
        files={"file": ("test.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test.png"
    assert data["media_type"] == "image"

    # Verify content headers
    asset_id = data["id"]
    content_resp = client.get(f"/api/v1/assets/{asset_id}/content")
    assert content_resp.status_code == 200
    assert content_resp.headers.get("x-content-type-options") == "nosniff"
    assert content_resp.headers.get("x-frame-options") == "DENY"
    assert "default-src 'none'" in content_resp.headers.get("content-security-policy", "")


def test_reject_html_upload():
    html_payload = b"<!DOCTYPE html><html><body><script>alert('pwned')</script></body></html>"
    response = client.post(
        "/api/v1/creative/upload",
        files={"file": ("exploit.html", io.BytesIO(html_payload), "text/html")},
    )
    assert response.status_code == 400
    assert "Active or executable content" in response.json()["detail"]


def test_reject_svg_upload():
    svg_payload = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    response = client.post(
        "/api/v1/creative/upload",
        files={"file": ("vector.svg", io.BytesIO(svg_payload), "image/svg+xml")},
    )
    assert response.status_code == 400
    assert "Active or executable content" in response.json()["detail"]


def test_reject_malformed_unsupported_media():
    garbage = b"this is not an image or video"
    response = client.post(
        "/api/v1/creative/upload",
        files={"file": ("bad.png", io.BytesIO(garbage), "image/png")},
    )
    assert response.status_code == 400
    assert "Unsupported or unrecognized media format" in response.json()["detail"]


def test_reject_oversized_dimensions():
    # Construct PNG with dimension > 8192
    huge_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        + struct.pack(">II", 10000, 10000)
        + b"\x08\x06\x00\x00\x00\x00\x00\x00\x00"
    )
    response = client.post(
        "/api/v1/creative/upload",
        files={"file": ("huge.png", io.BytesIO(huge_png), "image/png")},
    )
    assert response.status_code == 400
    assert "Image dimensions" in response.json()["detail"]
