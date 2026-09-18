import argparse
import shutil
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

from fidelity_fusion import fuse


ROOT = Path(__file__).resolve().parent
CLI = ROOT / "runtime" / "source" / "inference_cli.py"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--fusion-amount", type=float, default=0.28)
    parser.add_argument("--scale", type=float, choices=(1.5, 2.0), default=2.0)
    parser.add_argument("--raw-output-only", action="store_true")
    parser.add_argument("--save-raw", action="store_true")
    parser.add_argument("--no-explorer", action="store_true")
    args = parser.parse_args()
    if not 0.0 <= args.fusion_amount <= 0.5:
        parser.error("--fusion-amount must be between 0 and 0.5")
    source = args.source.resolve()
    with Image.open(source) as image:
        normalized = ImageOps.exif_transpose(image)
        width, height = normalized.size
    short = min(width, height)
    target_short = min(2560, max(1024, round(short * args.scale)))
    if target_short % 2:
        target_short += 1
    stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    if args.raw_output_only:
        output = source.with_name(f"{source.stem}_SeedVR2_raw_{stamp}.png")
    else:
        strength = round(args.fusion_amount * 100)
        output = source.with_name(f"{source.stem}_ClearScale_Fidelity_{strength}_{stamp}.png")
    job = Path(tempfile.mkdtemp(prefix="clearscale_seedvr2_"))
    staged_input = job / "input.png"
    staged_output = job / "output.png"
    with Image.open(source) as image:
        ImageOps.exif_transpose(image).save(staged_input, format="PNG")
    command = [
        sys.executable, str(CLI), str(staged_input), "--output", str(staged_output), "--output_format", "png",
        "--dit_model", "seedvr2_ema_3b-Q4_K_M.gguf",
        "--resolution", str(target_short), "--max_resolution", "4096", "--batch_size", "1",
        "--seed", "42", "--color_correction", "lab", "--input_noise_scale", "0",
        "--latent_noise_scale", "0", "--cuda_device", "0", "--dit_offload_device", "cpu",
        "--vae_offload_device", "cpu", "--tensor_offload_device", "cpu",
        "--blocks_to_swap", "32", "--swap_io_components", "--vae_encode_tiled",
        "--vae_decode_tiled", "--vae_encode_tile_size", "512", "--vae_decode_tile_size", "512",
        "--vae_encode_tile_overlap", "64", "--vae_decode_tile_overlap", "64",
        "--attention_mode", "sdpa", "--debug",
    ]
    inference_log = ROOT / "inference.log"
    print(f"Input: {width}x{height}; requested short side: {target_short}", flush=True)
    print(f"Full inference log: {inference_log}", flush=True)
    try:
        with inference_log.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                command, cwd=CLI.parent, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
            )
            assert process.stdout is not None
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
                log.flush()
            code = process.wait()
        if code:
            raise RuntimeError(f"SeedVR2 exited with code {code}. Read: {inference_log}")
        if not staged_output.exists():
            raise RuntimeError(f"CLI finished without expected output. Read: {inference_log}")
        with Image.open(staged_output) as result:
            result.verify()
        if args.raw_output_only:
            shutil.copy2(staged_output, output)
            fusion_report = {"mode": "raw SeedVR2 output"}
        else:
            try:
                fusion_report = fuse(source, staged_output, output, args.fusion_amount)
            except Exception as exc:
                with inference_log.open("a", encoding="utf-8") as log:
                    log.write("\nPOST-PROCESSING ERROR — raw output preserved\n")
                    log.write(traceback.format_exc())
                shutil.copy2(staged_output, output)
                fusion_report = {"mode": "raw fallback", "postprocess_error": str(exc)}
                print(f"WARNING: fidelity fusion failed; raw result preserved as {output}", flush=True)
            if args.save_raw:
                raw_output = source.with_name(f"{source.stem}_SeedVR2_raw_{stamp}.png")
                shutil.copy2(staged_output, raw_output)
                print(f"RAW: {raw_output}", flush=True)
        print(f"SUCCESS: {output}", flush=True)
        print(f"FUSION: {fusion_report}", flush=True)
        verifier = ROOT / "verify_result.py"
        if verifier.exists():
            subprocess.run([sys.executable, str(verifier), str(source), str(output)], check=False)
        if sys.platform == "win32" and not args.no_explorer:
            subprocess.run(["explorer.exe", f'/select,"{output}"'], check=False)
    finally:
        shutil.rmtree(job, ignore_errors=True)


if __name__ == "__main__":
    main()
