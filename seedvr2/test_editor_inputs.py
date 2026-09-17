import numpy as np

from app import editor_mask, editor_parts, image_pixels, populate_mask_editor


image = np.full((24, 32, 3), 127, dtype=np.uint8)
paint = np.zeros((24, 32, 4), dtype=np.uint8)
paint[4:12, 6:18, 3] = 255

# Normal Gradio payload.
background, mask = editor_parts({"background": image, "layers": [paint], "composite": image})
assert background.shape == image.shape
assert mask.shape == image.shape[:2]

# Payload observed on some Chromium/Gradio combinations: the visible upload is
# present as composite but background is null.
background, mask = editor_parts({"background": None, "layers": [paint], "composite": image})
assert np.array_equal(background, image)
assert int(mask.max()) == 255

# Image references use the same compatibility conversion.
assert np.array_equal(image_pixels({"background": None, "layers": [], "composite": image}), image)

# The dedicated upload is authoritative and is copied into the paint-only
# editor, avoiding browser-specific source/background serialization.
seeded = populate_mask_editor(image)
assert np.array_equal(seeded["background"], image)
assert seeded["layers"] == []
assert editor_mask({"background": None, "layers": [paint], "composite": None}).shape == image.shape[:2]

print("image editor compatibility test passed")

# Empty optional editors must not activate the pose stage or require a mask.
import tempfile
from pathlib import Path
from unittest.mock import patch
import app
empty = {"background": None, "layers": [], "composite": None}
assert not app.reference_present(empty)
assert not app.reference_present(None)
reference = {"background": image, "layers": [], "composite": image}
source = {"background": image, "layers": [paint], "composite": image}
with tempfile.TemporaryDirectory() as directory:
    with patch.object(app, "OUTPUTS", Path(directory)):
        job = app.process(image, source, empty, reference, empty, empty,
                          "自动分析（建议）", "Balanced 28%", 2, False,
                          .65, 4, 4, 320, .75, .9)
        with patch.object(app.subprocess, "Popen") as inference:
            status = next(job)[1]
            assert "Reference mask coverage" in status
            inference.assert_not_called()
        job.close()
print("empty optional reference regression passed")

# Local inpaint must finish all preprocessing and emit its first preview before
# any GPU subprocess is created. This catches missing imports in that path.
local_paint = np.zeros((24, 32, 4), dtype=np.uint8)
local_paint[2:22, 4:28, 3] = 255
local_editor = {"background": image, "layers": [local_paint], "composite": image}
with tempfile.TemporaryDirectory() as directory:
    with patch.object(app, "OUTPUTS", Path(directory)):
        job = app.local_inpaint(image, local_editor, empty, 10, 0, .35, .12,
                                .65, .8, .35, 42, "regular filament")
        preview, status, download = next(job)
        assert len(preview) == 3
        assert "本次仅修改整图" in status
        assert download is None
        job.close()
print("local inpaint preprocessing regression passed")
