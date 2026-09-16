import ast
import py_compile
from pathlib import Path


root = Path(__file__).resolve().parent
source = root / "runtime" / "source"
cli = source / "inference_cli.py"
assert cli.exists(), "Pinned SeedVR2 source is missing"
text = cli.read_text(encoding="utf-8")
for option in (
    "--dit_model", "--resolution", "--max_resolution", "--color_correction",
    "--blocks_to_swap", "--swap_io_components", "--vae_encode_tiled", "--vae_decode_tiled",
):
    assert option in text, f"Pinned CLI no longer supports {option}"
ast.parse(text)
py_compile.compile(str(root / "bootstrap.py"), doraise=True)
py_compile.compile(str(root / "run_seedvr2.py"), doraise=True)
assert "seedvr2_ema_3b-Q4_K_M.gguf" in (source / "README.md").read_text(encoding="utf-8")
print("Pinned SeedVR2 source and launcher scripts validated")
