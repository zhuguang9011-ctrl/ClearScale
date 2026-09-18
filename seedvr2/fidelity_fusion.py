"""Conservative luminance-detail fusion for product images.

The resized source remains the image. SeedVR2 contributes only aligned high-frequency
detail where it does not reduce the source's local detail energy. Source colour and alpha
are retained. This is deliberately not a generative quality score or semantic mask.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps


def blur(values: np.ndarray, radius: float) -> np.ndarray:
    image = Image.fromarray(np.uint8(np.clip(values, 0, 255)), mode="L")
    return np.asarray(image.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32)


def fuse_region(base: np.ndarray, seed: np.ndarray, amount: float):
    base_rgb = base[..., :3]
    seed_rgb = seed[..., :3]
    weights = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    base_y = base_rgb @ weights
    seed_y = seed_rgb @ weights

    base_detail = base_y - blur(base_y, 1.2)
    seed_detail = seed_y - blur(seed_y, 1.2)
    base_energy = blur(np.abs(base_detail) * 8.0, 2.0) / 8.0
    seed_energy = blur(np.abs(seed_detail) * 8.0, 2.0) / 8.0

    by, bx = np.gradient(base_y)
    sy, sx = np.gradient(seed_y)
    alignment = (bx * sx + by * sy) / (
        np.hypot(bx, by) * np.hypot(sx, sy) + 0.35
    )
    aligned = np.clip((alignment - 0.55) / 0.40, 0.0, 1.0)
    active = np.clip((base_energy - 0.20) / 1.30, 0.0, 1.0)
    detail_ratio = seed_energy / (base_energy + 0.45)
    non_destructive = np.clip((detail_ratio - 0.90) / 0.55, 0.0, 1.0)
    confidence = aligned * active * non_destructive

    detail_limit = np.abs(base_detail) * 1.75 + 2.0
    safe_seed_detail = np.clip(seed_detail, -detail_limit, detail_limit)
    delta_y = amount * confidence * (safe_seed_detail - base_detail)
    upper = 255.0 - np.max(base_rgb, axis=2)
    lower = np.min(base_rgb, axis=2)
    delta_y = np.minimum(np.maximum(delta_y, -lower), upper)
    fused_rgb = np.clip(base_rgb + delta_y[..., None], 0, 255)
    fused = np.concatenate([fused_rgb, base[..., 3:4]], axis=2).astype(np.uint8)
    return fused, confidence, delta_y


def fuse(source_path: Path, seed_path: Path, output_path: Path, amount: float = 0.28) -> dict:
    with Image.open(seed_path) as image:
        seed_rgba = ImageOps.exif_transpose(image).convert("RGBA")
    with Image.open(source_path) as image:
        source_rgba = ImageOps.exif_transpose(image).convert("RGBA").resize(
            seed_rgba.size, Image.Resampling.LANCZOS
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_image = source_rgba.copy()
    width, height = seed_rgba.size
    tile_size, padding = 512, 12
    confidence_sum = changed_count = delta_sum = pixel_count = 0.0
    max_delta = 0.0
    for top in range(0, height, tile_size):
        for left in range(0, width, tile_size):
            right, bottom = min(left + tile_size, width), min(top + tile_size, height)
            ext_left, ext_top = max(0, left - padding), max(0, top - padding)
            ext_right, ext_bottom = min(width, right + padding), min(height, bottom + padding)
            box = (ext_left, ext_top, ext_right, ext_bottom)
            base = np.asarray(source_rgba.crop(box), dtype=np.float32)
            seed = np.asarray(seed_rgba.crop(box), dtype=np.float32)
            fused, confidence, delta_y = fuse_region(base, seed, amount)
            x0, y0 = left - ext_left, top - ext_top
            x1, y1 = x0 + right - left, y0 + bottom - top
            core = fused[y0:y1, x0:x1]
            core_confidence = confidence[y0:y1, x0:x1]
            core_delta = delta_y[y0:y1, x0:x1]
            output_image.paste(Image.fromarray(core, mode="RGBA"), (left, top))
            count = core_confidence.size
            confidence_sum += float(core_confidence.sum())
            changed_count += float(np.count_nonzero(core_confidence * amount > 0.10))
            delta_sum += float(np.abs(core_delta).sum())
            max_delta = max(max_delta, float(np.max(np.abs(core_delta))))
            pixel_count += count
    output_image.save(output_path, format="PNG")

    report = {
        "mode": "source-preserving luminance detail fusion",
        "amount": amount,
        "size": list(seed_rgba.size),
        "processing": "512px low-memory tiles with overlap",
        "seed_contribution_mean": confidence_sum / pixel_count * amount,
        "seed_contribution_pixels_over_10_percent": changed_count / pixel_count,
        "mean_absolute_luminance_change_0_255": delta_sum / pixel_count,
        "max_absolute_luminance_change_0_255": max_delta,
        "source_color_and_alpha_preserved": True,
    }
    output_path.with_suffix(".fusion.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("seed", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--amount", type=float, default=0.28)
    args = parser.parse_args()
    if not 0.0 <= args.amount <= 0.5:
        parser.error("--amount must be between 0 and 0.5")
    print(json.dumps(fuse(args.source, args.seed, args.output, args.amount), indent=2))


if __name__ == "__main__":
    main()
