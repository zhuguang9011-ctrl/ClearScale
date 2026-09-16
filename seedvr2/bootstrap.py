import argparse
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

SOURCE_SHA = "4490bd1f482e026674543386bb2a4d176da245b9"
VERSION = "seedvr2-test-0.1.0"
ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "runtime"
SOURCE = RUNTIME / "source"
MARKER = RUNTIME / "installed.txt"


def run(command):
    print("+", " ".join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), check=True)


def install_source():
    sha_file = RUNTIME / "source-sha.txt"
    if (SOURCE / "inference_cli.py").exists() and sha_file.exists() and sha_file.read_text(encoding="utf-8", errors="ignore").strip() == SOURCE_SHA:
        return
    archive = RUNTIME / "seedvr2.zip"
    url = f"https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler/archive/{SOURCE_SHA}.zip"
    print("Downloading pinned SeedVR2 source...", flush=True)
    urllib.request.urlretrieve(url, archive)
    unpacked = RUNTIME / "source-unpacked"
    if unpacked.exists():
        shutil.rmtree(unpacked)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(unpacked)
    roots = [p for p in unpacked.iterdir() if p.is_dir()]
    if len(roots) != 1 or not (roots[0] / "inference_cli.py").exists():
        raise RuntimeError("Unexpected SeedVR2 source archive")
    if SOURCE.exists():
        shutil.rmtree(SOURCE)
    shutil.move(str(roots[0]), SOURCE)
    sha_file.write_text(SOURCE_SHA, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--uv", required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    RUNTIME.mkdir(exist_ok=True)
    install_source()
    if args.check_only:
        return
    expected = f"{VERSION}\n{SOURCE_SHA}\n"
    if MARKER.exists() and MARKER.read_text(encoding="utf-8", errors="ignore") == expected:
        print("Dependencies already prepared.")
        return
    run([args.uv, "pip", "install", "--python", sys.executable,
         "torch==2.9.1", "torchvision==0.24.1", "--index-url", "https://download.pytorch.org/whl/cu128"])
    run([args.uv, "pip", "install", "--python", sys.executable, "-r", SOURCE / "requirements.txt"])
    MARKER.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
