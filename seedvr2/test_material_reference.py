import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from material_reference import apply_reference


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    source = root / "source.png"
    output = root / "output.png"
    base = np.zeros((96, 96, 4), dtype=np.uint8)
    base[..., :3] = (95, 120, 145)
    base[..., 3] = np.arange(96, dtype=np.uint8)[None, :] + 150
    base[40:56, 40:56, :3] = 15
    Image.fromarray(base, mode="RGBA").save(source)
    y, x = np.mgrid[:48, :48]
    reference = np.stack([110 + ((x + y) % 5) * 5] * 3, axis=2).astype(np.uint8)
    mask = np.zeros((96, 96), dtype=np.uint8)
    mask[8:88, 8:88] = 255
    report = apply_reference(source, reference, mask, output, strength=1.5, texture_size=48)
    result = np.asarray(Image.open(output).convert("RGBA"))
    assert np.array_equal(result[..., 3], base[..., 3])
    assert np.array_equal(result[:3, :3, :3], base[:3, :3, :3])
    assert np.mean(np.abs(result[15:35, 15:35, :3].astype(float) - base[15:35, 15:35, :3])) > 0.05
    assert report["masked_fraction"] > 0.5
    assert report["mean_absolute_luminance_change_0_255"] < 2.0

print("material reference test passed")
