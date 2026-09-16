"""Masked, structure-safe microtexture transfer from a material reference image."""
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
    tile_y = np.asarray(tile.convert("L"), dtype=np.float32)
    tile_low = np.asarray(tile.convert("L").filter(ImageFilter.GaussianBlur(2.0)), dtype=np.float32)
    texture = tile_y - tile_low
    scale = float(np.percentile(np.abs(texture), 95))
    if scale < 0.25:
        raise ValueError("Reference image has too little visible surface texture")
    texture = np.clip(texture / scale, -1.5, 1.5)
    mirrored = np.block([[texture, texture[:, ::-1]],
                         [texture[::-1, :], texture[::-1, ::-1]]])
    pattern_size = texture_size * 2
    texture = np.tile(mirrored, ((height + pattern_size - 1) // pattern_size,
                                 (width + pattern_size - 1) // pattern_size))[:height, :width]

    mask_image = Image.fromarray(np.uint8(mask)).convert("L").resize((width, height), Image.Resampling.BILINEAR)
    mask_image = mask_image.filter(ImageFilter.GaussianBlur(3.0))
    mask_values = np.asarray(mask_image, dtype=np.float32) / 255.0
    if float(mask_values.max()) < 0.05:
        raise ValueError("Paint the target material area before using a reference image")

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
        "mode": "masked reference microtexture",
        "strength_luma": float(strength),
        "texture_size": int(texture_size),
        "masked_fraction": float(np.mean(mask_values > 0.1)),
        "mean_absolute_luminance_change_0_255": float(np.mean(np.abs(delta))),
        "structure_and_color_source": "ClearScale fidelity output",
    }
    output_path.with_suffix(".reference.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
