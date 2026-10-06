# Mask Normalization Implementation (Issue #106)

## Berry Mask Convention

**Canonical Semantic**: Painted regions (opaque white, alpha=255) indicate areas TO BE EDITED by AI. Unpainted regions (transparent, alpha=0) indicate areas TO BE PROTECTED.

This convention is documented in:
- `backend/app/runners/mask_converter.py` module docstring
- Test suite in `backend/tests/test_mask_converter.py`

## Provider-Specific Conversions

### ComfyUI
- **Contract**: LoadImage MASK output = `1 - alpha`
- **Issue**: Painted regions (alpha=255) become 0 (protect), transparent (alpha=0) becomes 1 (edit)
- **Solution**: Invert alpha channel before upload
- **Implementation**: `normalize_mask_for_comfyui()` creates temporary inverted mask

### WebUI
- **Contract**: Grayscale where white=edit, black=protect
- **Match**: Semantically matches Berry convention
- **Solution**: Convert RGBA alpha channel to grayscale L mode
- **Implementation**: `normalize_mask_for_webui()` extracts alpha to grayscale

### OpenAI
- **Contract**: Alpha channel where transparent=edit, opaque=protect
- **Issue**: Inverted from Berry convention
- **Solution**: Invert alpha channel
- **Implementation**: `normalize_mask_for_openai()` inverts alpha

### Fal.ai
- **Contract**: Alpha channel where opaque=edit, transparent=protect
- **Match**: Exactly matches Berry convention
- **Solution**: Validate format only, no conversion needed
- **Implementation**: `normalize_mask_for_fal_ai()` validates image

## Integration Points

1. **ComfyUI**: `creative_runner._run_comfy()` converts mask before upload, cleans up temporary file
2. **WebUI**: `webui_runner._run_inpaint()` converts mask before base64 encoding
3. **Cloud**: `creative_runner._run_cloud()` converts based on provider_id
4. **Validation**: All paths validate source/mask dimension alignment

## Cache Invalidation

Runner version bumped from `0.1.0` to `0.2.0` in `compute_creative_cache_hash()` to prevent reuse of results generated with incorrect mask semantics.

## Test Coverage

13 mask converter tests verify:
- Berry convention documentation
- Provider-specific conversions (ComfyUI, WebUI, OpenAI, Fal.ai)
- Dimension validation and preservation
- Edge cases: partial alpha, fully painted, fully transparent
- File handle management

All tests passing.
