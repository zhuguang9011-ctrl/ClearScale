"""Masked line-arrangement transfer that preserves the target image's colour."""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def apply_reference(image_path, reference, mask, output_path, strength=1.2, texture_size=320):
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
    tile_coarse = np.asarray(tile_luma.filter(ImageFilter.GaussianBlur(5.0)), dtype=np.float32)
    micro = tile_y - tile_fine
    meso = tile_fine - tile_coarse
    micro_scale = float(np.percentile(np.abs(micro), 95))
    meso_scale = float(np.percentile(np.abs(meso), 95))
    if max(micro_scale, meso_scale) < 0.25:
        raise ValueError("Reference image has too little visible surface texture")
    micro /= max(micro_scale, 0.25)
    meso /= max(meso_scale, 0.25)
    texture = np.clip(micro * 0.65 + meso * 0.35, -1.5, 1.5)
    mirrored = np.block([[texture, texture[:, ::-1]],
                         [texture[::-1, :], texture[::-1, ::-1]]])
    pattern_size = texture_size * 2
    texture = np.tile(mirrored, ((height + pattern_size - 1) // pattern_size,
                                 (width + pattern_size - 1) // pattern_size))[:height, :width]

    mask_image = Image.fromarray(np.uint8(mask)).convert("L").resize((width, height), Image.Resampling.BILINEAR)
    mask_image = mask_image.filter(ImageFilter.GaussianBlur(3.0))
    mask_values = np.asarray(mask_image, dtype=np.float32) / 255.0
    masked_fraction = float(np.mean(mask_values > 0.1))
    if float(mask_values.max()) < 0.05:
        raise ValueError("Paint the target material area before using a reference image")
    if masked_fraction < 0.01:
        raise ValueError("Paint a larger target surface; the current mask covers less than 1% of the image")

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
        "mode": "masked grayscale line-arrangement transfer",
        "strength_luma": float(strength),
        "texture_size": int(texture_size),
        "masked_fraction": masked_fraction,
        "mean_absolute_luminance_change_0_255": float(np.mean(np.abs(delta))),
        "reference_detail_bands": "micro 65% + meso 35%",
        "reference_role": "line spacing, parallel arrangement and surface relief only",
        "reference_color_transferred": False,
        "structure_and_color_source": "ClearScale fidelity output",
    }
    output_path.with_suffix(".reference.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
