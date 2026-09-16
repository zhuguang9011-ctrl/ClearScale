import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from fidelity_fusion import fuse


def detail_energy(image):
    gray = image.convert("L")
    values = np.asarray(gray, dtype=np.float32)
    blurred = np.asarray(gray.filter(ImageFilter.GaussianBlur(1.2)), dtype=np.float32)
    return float(np.mean(np.abs(values - blurred)))


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    source_path = root / "source.png"
    seed_path = root / "seed.png"
    output_path = root / "output.png"

    y, x = np.mgrid[:64, :64]
    stripes = ((x // 2) % 2) * 36 + 100
    rgba = np.zeros((64, 64, 4), dtype=np.uint8)
    rgba[..., 0] = stripes
    rgba[..., 1] = stripes + 20
    rgba[..., 2] = stripes + 35
    rgba[..., 3] = np.uint8(np.linspace(40, 255, 64))[None, :]
    source = Image.fromarray(rgba, mode="RGBA")
    source.save(source_path)

    base = source.resize((128, 128), Image.Resampling.LANCZOS)
    smoothed = base.convert("RGB").filter(ImageFilter.GaussianBlur(2.0))
    smoothed.save(seed_path)
    report = fuse(source_path, seed_path, output_path, amount=0.40)
    output = Image.open(output_path).convert("RGBA")

    assert output.size == (128, 128)
    assert np.array_equal(np.asarray(output)[..., 3], np.asarray(base)[..., 3])
    assert detail_energy(output) >= detail_energy(base) * 0.99
    assert report["source_color_and_alpha_preserved"] is True
    assert report["seed_contribution_mean"] < 0.01

print("fidelity fusion test passed")
