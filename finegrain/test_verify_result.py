import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    source = root / "source.png"
    result = root / "result.png"
    pixels = np.zeros((24, 32, 3), dtype=np.uint8)
    pixels[:, :16] = (30, 80, 140)
    pixels[:, 16:] = (210, 170, 90)
    Image.fromarray(pixels).save(source)
    Image.fromarray(pixels).resize((64, 48), Image.Resampling.LANCZOS).save(result)
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("verify_result.py")), str(source), str(result)],
        check=True,
        capture_output=True,
        text=True,
    )
    report_line = completed.stdout.split("Report:", 1)[1].strip()
    report = json.loads(Path(report_line).read_text(encoding="utf-8"))
    assert report["output_decode_pass"] is True
    assert report["comparison"]["scale_xy"] == [2.0, 2.0]
    assert report["comparison"]["aspect_ratio_relative_error"] == 0.0
    assert report["comparison"]["edge_map_correlation"] > 0.9

print("verification report test passed")
