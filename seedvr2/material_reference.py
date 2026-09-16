"""Masked, decomposed reference transfer that preserves the target image's colour."""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


FEATURE_WEIGHTS = {
    "arrangement": (0.20, 0.70, 0.10),
    "microtexture": (0.80, 0.15, 0.05),
    "finish": (0.05, 0.25, 0.70),
    "material": (0.45, 0.35, 0.20),
}


def _soft_mask(mask, size):
    mask_image = Image.fromarray(np.uint8(mask)).convert("L").resize(size, Image.Resampling.BILINEAR)
    mask_image = mask_image.filter(ImageFilter.GaussianBlur(3.0))
    values = np.asarray(mask_image, dtype=np.float32) / 255.0
    fraction = float(np.mean(values > 0.1))
    if float(values.max()) < 0.05:
        raise ValueError("Paint the target area before using a reference image")
    if fraction < 0.01:
        raise ValueError("Paint a larger target surface; the current mask covers less than 1% of the image")
    return values, fraction


def apply_color_reference(image_path, reference, mask, output_path, strength=0.65):
    """Transfer robust reference chroma while preserving target luminance and alpha."""
    image_path, output_path = Path(image_path), Path(output_path)
    with Image.open(image_path) as image:
        base_image = image.convert("RGBA")
    width, height = base_image.size
    mask_values, masked_fraction = _soft_mask(mask, (width, height))
    base_ycc = np.asarray(base_image.convert("RGB").convert("YCbCr"), dtype=np.float32)
    reference_ycc = np.asarray(
        Image.fromarray(np.uint8(reference)).convert("RGB").convert("YCbCr"), dtype=np.float32
    )
    reference_chroma = np.median(reference_ycc[..., 1:3].reshape(-1, 2), axis=0)
    blend = np.clip(float(strength), 0.0, 1.0) * mask_values[..., None]
    result_ycc = base_ycc.copy()
    result_ycc[..., 1:3] = (
        base_ycc[..., 1:3] * (1.0 - blend) + reference_chroma[None, None, :] * blend
    )
    result_rgb = np.asarray(
        Image.fromarray(np.uint8(np.clip(result_ycc, 0, 255)), mode="YCbCr").convert("RGB")
    )
    alpha = np.asarray(base_image)[..., 3:4]
    result = np.concatenate([result_rgb, alpha], axis=2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(result, mode="RGBA").save(output_path, format="PNG")
    report = {
        "mode": "masked chroma-only reference transfer",
        "strength": float(strength),
        "masked_fraction": masked_fraction,
        "target_luminance_preserved": True,
        "target_alpha_preserved": True,
        "reference_chroma_ycbcr": [float(value) for value in reference_chroma],
    }
    output_path.with_suffix(".color.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def apply_reference(image_path, reference, mask, output_path, strength=1.2,
                    texture_size=320, feature_mode="auto"):
    image_path, output_path = Path(image_path), Path(output_path)
    with Image.open(image_path) as image:
        base_image = image.convert("RGBA")
    base = np.asarray(base_image, dtype=np.float32)
    height, width = base.shape[:2]

    reference_image = Image.fromarray(np.uint8(reference)).convert("RGB")
    tile = reference_image.resize((texture_size, texture_size), Image.Resampling.LANCZOS)
    tile_luma = tile.convert("L")
    tile_y = np.asarray(tile_luma, dtype=np.float32)
    tile_fine = np.asarray(tile_luma.filter(ImageFilter.GaussianBlur(1.2)), dtype=np.float32)
    tile_medium = np.asarray(tile_luma.filter(ImageFilter.GaussianBlur(5.0)), dtype=np.float32)
    tile_coarse = np.asarray(tile_luma.filter(ImageFilter.GaussianBlur(14.0)), dtype=np.float32)
    micro = tile_y - tile_fine
    meso = tile_fine - tile_medium
    finish = tile_medium - tile_coarse
    scales = np.array([
        float(np.percentile(np.abs(micro), 95)),
        float(np.percentile(np.abs(meso), 95)),
        float(np.percentile(np.abs(finish), 95)),
    ], dtype=np.float32)
    if float(scales.max()) < 0.25:
        raise ValueError("Reference image has too little visible surface texture")
    bands = [micro / max(float(scales[0]), 0.25),
             meso / max(float(scales[1]), 0.25),
             finish / max(float(scales[2]), 0.25)]
    if feature_mode == "auto":
        weights = np.sqrt(np.maximum(scales, 0.01))
        weights /= weights.sum()
    else:
        if feature_mode not in FEATURE_WEIGHTS:
            raise ValueError(f"Unknown reference feature mode: {feature_mode}")
        weights = np.asarray(FEATURE_WEIGHTS[feature_mode], dtype=np.float32)
    texture = np.clip(sum(weight * band for weight, band in zip(weights, bands)), -1.5, 1.5)
    mirrored = np.block([[texture, texture[:, ::-1]],
                         [texture[::-1, :], texture[::-1, ::-1]]])
    pattern_size = texture_size * 2
    texture = np.tile(mirrored, ((height + pattern_size - 1) // pattern_size,
                                 (width + pattern_size - 1) // pattern_size))[:height, :width]

    mask_values, masked_fraction = _soft_mask(mask, (width, height))

    rgb = base[..., :3]
    luminance = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    gy, gx = np.gradient(luminance)
    edge_protection = np.exp(-np.square(np.hypot(gx, gy) / 10.0))
    delta = texture * float(strength) * mask_values * edge_protection
    upper = 255.0 - np.max(rgb, axis=2)
    lower = np.min(rgb, axis=2)
    delta = np.minimum(np.maximum(delta, -lower), upper)
    result = np.concatenate([np.clip(rgb + delta[..., None], 0, 255), base[..., 3:4]], axis=2).astype(np.uint8)
    Image.fromarray(result, mode="RGBA").save(output_path, format="PNG")
    report = {
        "mode": "masked decomposed grayscale reference transfer",
        "reference_feature_mode": feature_mode,
        "reference_feature_weights_micro_meso_finish": [float(value) for value in weights],
        "strength_luma": float(strength),
        "texture_size": int(texture_size),
        "masked_fraction": masked_fraction,
        "mean_absolute_luminance_change_0_255": float(np.mean(np.abs(delta))),
        "reference_detail_bands": "micro + meso + finish",
        "reference_color_transferred": False,
        "structure_and_color_source": "ClearScale fidelity output",
    }
    output_path.with_suffix(".reference.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
