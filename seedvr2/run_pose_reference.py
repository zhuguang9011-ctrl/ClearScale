"""Optional product pose/layout reconstruction using IP-Adapter + ControlNet.

The heavy diffusion dependencies and weights are installed/downloaded only when this
script is invoked. It is intentionally separate from the deterministic SeedVR2 path.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parent
POSE_MARKER = ROOT / "runtime" / "pose-installed.txt"
POSE_VERSION = "sd15-ipadapter-controlnet-pose-0.1"


def install_dependencies():
    if POSE_MARKER.exists() and POSE_MARKER.read_text(encoding="utf-8").strip() == POSE_VERSION:
        return
    uv = ROOT / "runtime" / "uv.exe"
    if not uv.exists():
        raise RuntimeError("Run Start.cmd once before enabling pose reference")
    command = [
        str(uv), "pip", "install", "--python", sys.executable,
        "diffusers==0.35.1", "accelerate==1.10.1",
    ]
    print("Installing optional pose-reference dependencies...", flush=True)
    subprocess.run(command, check=True)
    POSE_MARKER.write_text(POSE_VERSION, encoding="utf-8")


def fit_size(size, longest=768):
    width, height = size
    factor = min(1.0, longest / max(width, height))
    width = max(256, int(round(width * factor / 8)) * 8)
    height = max(256, int(round(height * factor / 8)) * 8)
    return width, height


def prepare_identity(source, source_mask, size):
    source = ImageOps.exif_transpose(source).convert("RGB")
    mask = ImageOps.exif_transpose(source_mask).convert("L").resize(source.size, Image.Resampling.BILINEAR)
    values = np.asarray(mask)
    points = np.argwhere(values > 25)
    if points.size == 0:
        raise ValueError("Paint the product on the source image before using pose reference")
    y0, x0 = points.min(axis=0)
    y1, x1 = points.max(axis=0) + 1
    pad = max(8, int(max(x1 - x0, y1 - y0) * 0.08))
    box = (max(0, x0 - pad), max(0, y0 - pad), min(source.width, x1 + pad), min(source.height, y1 + pad))
    crop = source.crop(box)
    crop_mask = mask.crop(box)
    white = Image.new("RGB", crop.size, "white")
    white.paste(crop, mask=crop_mask)
    return ImageOps.contain(white, size, Image.Resampling.LANCZOS)


def prepare_control(pose, pose_mask, size):
    pose = ImageOps.exif_transpose(pose).convert("RGB").resize(size, Image.Resampling.LANCZOS)
    mask = ImageOps.exif_transpose(pose_mask).convert("L").resize(size, Image.Resampling.BILINEAR)
    try:
        import cv2
        gray = cv2.cvtColor(np.asarray(pose), cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 100, 200)
    except ImportError:
        found = np.asarray(pose.convert("L").filter(ImageFilter.FIND_EDGES), dtype=np.uint8)
        edges = np.where(found > 24, 255, 0).astype(np.uint8)
    edges[np.asarray(mask) < 25] = 0
    return Image.fromarray(np.repeat(edges[..., None], 3, axis=2), mode="RGB")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("source_mask", type=Path)
    parser.add_argument("pose_reference", type=Path)
    parser.add_argument("pose_mask", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--identity-strength", type=float, default=0.75)
    parser.add_argument("--pose-strength", type=float, default=0.90)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    install_dependencies()

    import torch
    from diffusers import ControlNetModel, StableDiffusionControlNetPipeline, UniPCMultistepScheduler

    with Image.open(args.pose_reference) as image:
        size = fit_size(image.size)
    with Image.open(args.source) as source, Image.open(args.source_mask) as source_mask:
        identity = prepare_identity(source, source_mask, size)
    with Image.open(args.pose_reference) as pose, Image.open(args.pose_mask) as pose_mask:
        control = prepare_control(pose, pose_mask, size)

    print("Loading optional pose engine (first use downloads several model files)...", flush=True)
    dtype = torch.float16
    controlnet = ControlNetModel.from_pretrained(
        "lllyasviel/control_v11p_sd15_canny", torch_dtype=dtype,
    )
    pipe = StableDiffusionControlNetPipeline.from_pretrained(
        "stable-diffusion-v1-5/stable-diffusion-v1-5",
        controlnet=controlnet, torch_dtype=dtype, safety_checker=None,
        requires_safety_checker=False,
    )
    pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)
    pipe.load_ip_adapter(
        "h94/IP-Adapter", subfolder="models", weight_name="ip-adapter-plus_sd15.bin",
    )
    pipe.set_ip_adapter_scale(float(args.identity_strength))
    pipe.enable_model_cpu_offload()
    pipe.enable_vae_slicing()
    pipe.enable_vae_tiling()
    generator = torch.Generator(device="cpu").manual_seed(args.seed)
    result = pipe(
        prompt="commercial studio product photograph, same product, accurate geometry, clean background, realistic materials",
        negative_prompt="text, watermark, logo, duplicate product, extra objects, distorted geometry, deformed, illustration",
        image=control,
        ip_adapter_image=identity,
        width=size[0], height=size[1], num_inference_steps=28, guidance_scale=4.5,
        controlnet_conditioning_scale=float(args.pose_strength), generator=generator,
    ).images[0]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.save(args.output, format="PNG")
    report = {
        "mode": "experimental product identity + pose reconstruction",
        "identity_strength": float(args.identity_strength),
        "pose_strength": float(args.pose_strength),
        "size": list(size),
        "seed": args.seed,
        "models": ["stable-diffusion-v1-5", "IP-Adapter Plus SD15", "ControlNet Canny SD15"],
    }
    args.output.with_suffix(".pose.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"POSE SUCCESS: {args.output}", flush=True)


if __name__ == "__main__":
    main()
