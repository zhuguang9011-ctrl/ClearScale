import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from material_reference import apply_color_reference, apply_reference


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
    report = apply_reference(source, reference, mask, output, strength=4.0,
                             texture_size=48, feature_mode="auto")
    result = np.asarray(Image.open(output).convert("RGBA"))
    assert np.array_equal(result[..., 3], base[..., 3])
    assert np.array_equal(result[:3, :3, :3], base[:3, :3, :3])
    assert np.mean(np.abs(result[15:35, 15:35, :3].astype(float) - base[15:35, 15:35, :3])) > 0.05
    assert report["masked_fraction"] > 0.5
    assert 0.05 < report["mean_absolute_luminance_change_0_255"] < 5.0
    assert report["reference_detail_bands"] == "micro + meso + finish"
    assert report["reference_color_transferred"] is False
    # An equal luminance delta is applied to R/G/B, so target channel spacing
    # (and therefore target chroma) must remain intact away from clipping.
    target = result[15:35, 15:35, :3].astype(np.int16)
    original = base[15:35, 15:35, :3].astype(np.int16)
    assert np.max(np.abs((target[..., 1] - target[..., 0]) -
                         (original[..., 1] - original[..., 0]))) <= 1
    assert np.max(np.abs((target[..., 2] - target[..., 1]) -
                         (original[..., 2] - original[..., 1]))) <= 1

    for feature_mode in ("arrangement", "microtexture", "finish", "material"):
        mode_output = root / f"{feature_mode}.png"
        mode_report = apply_reference(
            source, reference, mask, mode_output, strength=4.0,
            texture_size=48, feature_mode=feature_mode,
        )
        assert mode_output.exists()
        assert mode_report["reference_feature_mode"] == feature_mode
        assert mode_report["reference_color_transferred"] is False

    color_output = root / "color.png"
    color_reference = np.zeros((32, 32, 3), dtype=np.uint8)
    color_reference[..., :3] = (210, 55, 90)
    color_report = apply_color_reference(
        source, color_reference, mask, color_output, strength=0.65
    )
    color_result = np.asarray(Image.open(color_output).convert("RGBA"))
    assert np.array_equal(color_result[..., 3], base[..., 3])
    base_luma = np.asarray(Image.fromarray(base[..., :3]).convert("L"), dtype=np.int16)
    result_luma = np.asarray(Image.fromarray(color_result[..., :3]).convert("L"), dtype=np.int16)
    assert np.mean(np.abs(result_luma[15:35, 15:35] - base_luma[15:35, 15:35])) < 2.0
    assert color_report["target_luminance_preserved"] is True

print("material reference test passed")
