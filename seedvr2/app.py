import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import gradio as gr
import numpy as np
from PIL import Image

from material_reference import apply_reference


ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"


def editor_parts(value):
    if not isinstance(value, dict) or value.get("background") is None:
        raise gr.Error("Upload a source image first")
    background = np.asarray(value["background"])
    if np.issubdtype(background.dtype, np.floating) and float(background.max()) <= 1.0:
        background = background * 255.0
    layers = value.get("layers") or []
    mask = None
    for layer in layers:
        array = np.asarray(layer)
        if np.issubdtype(array.dtype, np.floating) and float(array.max()) <= 1.0:
            array = array * 255.0
        alpha = array[..., 3] if array.ndim == 3 and array.shape[2] >= 4 else np.max(array[..., :3], axis=2)
        mask = alpha if mask is None else np.maximum(mask, alpha)
    return background, mask


def process(editor, reference, mode, scale, save_raw, reference_strength, texture_size):
    background, mask = editor_parts(editor)
    if reference is not None and mask is None:
        raise gr.Error("Paint the target material area before applying a reference")
    if reference is not None:
        reference = np.asarray(reference)
        if np.issubdtype(reference.dtype, np.floating) and float(reference.max()) <= 1.0:
            reference = reference * 255.0
    job = OUTPUTS / datetime.now().strftime("job_%Y%m%d_%H%M%S_%f")
    job.mkdir(parents=True, exist_ok=True)
    source = job / "source.png"
    Image.fromarray(np.uint8(background)).save(source)
    amounts = {"Fidelity 15%": 0.15, "Balanced 28%": 0.28, "Detail 40%": 0.40}
    command = [sys.executable, str(ROOT / "run_seedvr2.py"), str(source), "--scale", str(scale), "--no-explorer"]
    if mode == "Raw SeedVR2":
        command += ["--raw-output-only"]
    else:
        command += ["--fusion-amount", str(amounts[mode])]
        if save_raw:
            command += ["--save-raw"]
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace")
    lines = []
    assert process.stdout is not None
    for line in process.stdout:
        lines.append(line.rstrip())
        yield [], "\n".join(lines[-18:]), None
    code = process.wait()
    if code:
        raise gr.Error("Processing failed. Read inference.log")
    candidates = sorted(job.glob("*_ClearScale_Fidelity_*.png"))
    raw = sorted(job.glob("*_SeedVR2_raw_*.png"))
    final = (candidates or raw)[-1]
    gallery = [(str(source), "Source")]
    if raw:
        gallery.append((str(raw[-1]), "Raw SeedVR2"))
    if reference is not None and mode != "Raw SeedVR2":
        referenced = job / "ClearScale_reference_result.png"
        apply_reference(final, reference, mask, referenced, reference_strength, int(texture_size))
        final = referenced
        gallery.append((str(final), "Fidelity + reference microtexture"))
    else:
        gallery.append((str(final), "Final"))
    yield gallery, "\n".join(lines[-18:]) + f"\nREADY: {final}", str(final)


def build_ui():
    css = """
    .gradio-container {max-width: 1600px !important; background:#15171b}
    .panel {border:1px solid #343841 !important; border-radius:12px !important; background:#1d2026 !important}
    """
    with gr.Blocks(title="ClearScale Material Studio", css=css, theme=gr.themes.Base()) as demo:
        gr.Markdown("# ClearScale Material Studio\nStructure-preserving upscale with optional masked material reference")
        with gr.Row():
            with gr.Column(scale=5, elem_classes="panel"):
                editor = gr.ImageEditor(label="1. Source image — paint only the material area when using a reference", type="numpy")
                reference = gr.Image(label="2. Optional material reference", type="numpy")
            with gr.Column(scale=3, elem_classes="panel"):
                mode = gr.Dropdown(["Fidelity 15%", "Balanced 28%", "Detail 40%", "Raw SeedVR2"], value="Balanced 28%", label="Detail mode")
                scale = gr.Radio([1.5, 2.0], value=2.0, label="Output scale")
                save_raw = gr.Checkbox(False, label="Also save raw SeedVR2 result")
                reference_strength = gr.Slider(0.0, 3.0, value=1.2, step=0.1, label="Reference microtexture strength")
                texture_size = gr.Slider(128, 640, value=320, step=32, label="Reference texture scale")
                run = gr.Button("Enhance", variant="primary")
                status = gr.Textbox(label="Console", lines=18)
            with gr.Column(scale=5, elem_classes="panel"):
                gallery = gr.Gallery(label="3. Results", columns=1, height=720, object_fit="contain")
                download = gr.File(label="Download final PNG")
        run.click(process, [editor, reference, mode, scale, save_raw, reference_strength, texture_size], [gallery, status, download])
    return demo.queue(default_concurrency_limit=1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    app = build_ui()
    if not args.check:
        OUTPUTS.mkdir(exist_ok=True)
        app.launch(server_name="127.0.0.1", inbrowser=True, show_error=True)
