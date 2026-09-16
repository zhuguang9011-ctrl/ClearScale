# Surface cleanup development checkpoint

This branch is an engineering checkpoint, not a validated material-restoration release.

## Implemented

- Separate CPU surface-cleanup mode, original-size PNG output, no external model installation.
- Edge-gated 3×3 chroma cleanup with original luminance preserved up to 8-bit rounding.
- Preserve original alpha; skip partially transparent pixels; reject inputs above 20 MP.
- Run in image worker; cancellation, output collision protection and batch handling.
- Display actual decoded output dimensions in ClearScale.
- Distinguish ClearScale preview load failure from successful file export.

## Verification

11 automated tests pass locally, including existing upscaler and mocked ComfyUI regression tests.
The new synthetic test checks reduced chroma noise, no luminance drift above 0.501/255,
alpha preservation, material-boundary protection and zero-strength identity.

User-supplied original product poster was processed locally at default strength 0.35:

- Input and output: 1254 × 1254.
- Pixels with changed RGB: 60,062 / 1,572,516 (about 3.82%).
- Alpha changes: 0 pixels.
- Maximum luminance change: 0.4304 / 255.
- Mean absolute luminance change: 0.005124 / 255.
- Measured processing time here: 1.387 seconds; not a Windows/GPU benchmark.

Visual inspection at overview scale: effect is very subtle, with no obvious composition
or surface-shape change. This does NOT demonstrate removal of plastic appearance,
recovery of authentic microtexture or repair of existing halos. No customer images
or generated customer samples are committed to this repository.

Finegrain completed real CUDA inference on the user's RTX 5060 Ti 8 GB and saved a readable PNG.
The supplied 1254 × 1254 source and 1536 × 1536 result preserve aspect ratio, but the actual
linear scale is about 1.225× rather than the selected 2×. Same-size comparison measured RGB MAE
4.545/255 and edge-map correlation 0.887. These are diagnostic measurements, not quality scores.
Visual review failed the product criterion: the result increased plastic/waxy rendering and a crop
showed white halos and smeared detail. Finegrain is therefore operational but rejected as the
production material-refinement engine.

A standalone SeedVR2 evaluation launcher is now included with a fixed 8 GB preset: 3B Q4 GGUF,
32-block swap, CPU offload, 512 px VAE tiling, LAB colour correction and zero noise injection.
It pins upstream source commit `4490bd1f482e026674543386bb2a4d176da245b9` and does not require
ComfyUI. Source/interface/package validation is automated; real model inference on the user's GPU
is still required before judging its visual suitability.

## Still unresolved

- Reliable material enhancement without hallucinated structure, changed colour or waxy surfaces.
- Real SeedVR2 model inference validation on the user's 5060 Ti 8 GB.
- Finegrain's preview now uses a native two-image Gradio gallery instead of the custom slider.
  Result-wrapper/API-cache regression passes locally with generated test images; this does not prove
  the cause of the original user's failure or validate actual model inference.
- Full desktop interaction validation for this new mode.

Do not replace the installed version or label this branch production-ready based only on unit tests.
