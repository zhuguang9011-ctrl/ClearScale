import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from run_pose_reference import fit_size, prepare_control, prepare_identity


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    source = np.full((160, 240, 3), 245, dtype=np.uint8)
    source[35:135, 70:180] = (25, 90, 160)
    source_mask = np.zeros((160, 240), dtype=np.uint8)
    source_mask[35:135, 70:180] = 255
    pose = np.full((180, 120, 3), 250, dtype=np.uint8)
    pose[25:155, 35:90] = (40, 40, 40)
    pose_mask = np.zeros((180, 120), dtype=np.uint8)
    pose_mask[20:160, 30:95] = 255
    size = fit_size((120, 180), longest=512)
    identity = prepare_identity(Image.fromarray(source), Image.fromarray(source_mask), size)
    control = prepare_control(Image.fromarray(pose), Image.fromarray(pose_mask), size)
    assert identity.size[0] <= size[0] and identity.size[1] <= size[1]
    assert control.size == size
    assert np.asarray(control).max() == 255
    assert np.all(np.asarray(control)[:10, :10] == 0)

print("pose reference preprocessing test passed")
