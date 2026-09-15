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

## Still unresolved

- Reliable material enhancement without hallucinated structure, changed colour or waxy surfaces.
- Real GPU inference validation on the user's 5060 Ti 8 GB.
- Finegrain's preview now uses a native two-image Gradio gallery instead of the custom slider.
  Result-wrapper/API-cache regression passes locally with generated test images; this does not prove
  the cause of the original user's failure or validate actual model inference.
- Full desktop interaction validation for this new mode.

Do not replace the installed version or label this branch production-ready based only on unit tests.
