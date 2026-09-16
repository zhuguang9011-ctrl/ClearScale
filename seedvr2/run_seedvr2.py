import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parent
CLI = ROOT / "runtime" / "source" / "inference_cli.py"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Expected one input image")
    source = Path(sys.argv[1]).resolve()
    with Image.open(source) as image:
        width, height = ImageOps.exif_transpose(image).size
    short = min(width, height)
    target_short = min(2048, max(1024, short * 2))
    output = source.with_name(f"{source.stem}_SeedVR2_{datetime.now():%Y%m%d_%H%M%S}.png")
    command = [
        sys.executable, str(CLI), str(source), "--output", str(output), "--output_format", "png",
        "--dit_model", "seedvr2_ema_3b-Q4_K_M.gguf",
        "--resolution", str(target_short), "--max_resolution", "3072", "--batch_size", "1",
        "--seed", "42", "--color_correction", "lab", "--input_noise_scale", "0",
        "--latent_noise_scale", "0", "--cuda_device", "0", "--dit_offload_device", "cpu",
        "--vae_offload_device", "cpu", "--tensor_offload_device", "cpu",
        "--blocks_to_swap", "32", "--swap_io_components", "--vae_encode_tiled",
        "--vae_decode_tiled", "--vae_encode_tile_size", "512", "--vae_decode_tile_size", "512",
        "--vae_encode_tile_overlap", "64", "--vae_decode_tile_overlap", "64",
        "--attention_mode", "sdpa", "--debug",
    ]
    print(f"Input: {width}x{height}; requested short side: {target_short}", flush=True)
    subprocess.run(command, cwd=CLI.parent, check=True)
    if not output.exists():
        raise RuntimeError(f"CLI finished without expected output: {output}")
    with Image.open(output) as result:
        result.verify()
    print(f"SUCCESS: {output}", flush=True)
    verifier = ROOT / "verify_result.py"
    if verifier.exists():
        subprocess.run([sys.executable, str(verifier), str(source), str(output)], check=False)
    if sys.platform == "win32":
        subprocess.run(["explorer.exe", "/select,", str(output)], check=False)


if __name__ == "__main__":
    main()
