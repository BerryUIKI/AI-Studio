# Inpainting Mask Contract (#106)

Berry masks encode edit coverage in alpha: opaque painted pixels are edited; transparent pixels are protected. Partial alpha preserves brush-edge coverage. Imported masks must have alpha; arbitrary grayscale uploads are not silently reinterpreted.

| Adapter | Submitted mask | Painted region | Protected region |
| --- | --- | --- | --- |
| ComfyUI LoadImage | RGBA PNG, inverse alpha | Alpha 0 -> MASK 1 | Alpha 255 -> MASK 0 |
| WebUI | Grayscale PNG from Berry alpha | White 255 | Black 0 |
| OpenAI edits | RGBA PNG, inverse alpha | Transparent | Opaque |
| Fal flux-general/inpainting | Grayscale PNG from Berry alpha | White 255 | Black 0 |

Fal uses an explicit grayscale mask rather than relying on transparency being interpreted consistently. Its documented [inpainting API](https://fal.ai/models/fal-ai/flux-general/inpainting/api) supplies a separate image and mask. [OpenAI mask guidance](https://developers.openai.com/api/docs/guides/image-generation) specifies transparent edit regions. ComfyUI LoadImage's mask remains inverse alpha.

Every creative inpaint submission validates mask dimensions against the actual source before cache lookup or inference. Mismatches fail with guidance rather than stretching or cropping. Conversions preserve exact dimensions and coordinates. Temporary Comfy masks have unique filenames and are removed after upload. CPU mask conversion runs in a worker thread on creative cloud/Comfy paths. Cache runner version 0.4.0 invalidates older semantics.

Validation: 16 converter and cloud adapter payload tests pass. An 8x6 source with one painted pixel asserts the exact Fal/OpenAI payload meaning and unchanged coordinate alignment; mismatched dimensions prevent dispatch. Existing creative/upload/cancellation tests also pass (28 tests).

These are deterministic adapter tests. Live engine/provider output preservation remains unverified; #106 stays open until a real known-region run records source, mask, output, engine/model/provider versions, and protected-area comparison. No paid inference was performed.
