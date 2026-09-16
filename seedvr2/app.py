import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import gradio as gr
import numpy as np
from PIL import Image

from material_reference import apply_color_reference, apply_reference


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


def image_pixels(value):
    """Accept gr.Image or gr.ImageEditor values and return the visible pixels."""
    if isinstance(value, dict):
        pixels = value.get("composite")
        if pixels is None:
            pixels = value.get("background")
    else:
        pixels = value
    if pixels is None:
        raise gr.Error("Upload and crop a material reference first")
    pixels = np.asarray(pixels)
    if np.issubdtype(pixels.dtype, np.floating) and float(pixels.max()) <= 1.0:
        pixels = pixels * 255.0
    return pixels


def process(editor, color_reference, material_reference, arrangement_reference,
            pose_reference, material_feature, mode, scale, save_raw, color_strength,
            material_strength, arrangement_strength, texture_size,
            pose_identity_strength, pose_structure_strength):
    background, source_mask = editor_parts(editor)
    references = [color_reference, material_reference, arrangement_reference]
    has_reference = any(value is not None for value in references)
    has_pose = pose_reference is not None
    if (has_reference or has_pose) and source_mask is None:
        raise gr.Error("Paint the target material area before applying a reference")
    source_mask_coverage = float(np.mean(source_mask > 25)) if source_mask is not None else 0.0
    if (has_reference or has_pose) and source_mask_coverage < 0.01:
        raise gr.Error("Paint a larger material surface. The current painted area is less than 1% of the image.")
    pose_background = pose_mask = None
    if has_pose:
        pose_background, pose_mask = editor_parts(pose_reference)
        if pose_mask is None or float(np.mean(pose_mask > 25)) < 0.01:
            raise gr.Error("Paint the desired product area on the pose/layout reference (at least 1%).")
    mask = pose_mask if has_pose else source_mask
    mask_coverage = float(np.mean(mask > 25)) if mask is not None else 0.0
    color_reference = image_pixels(color_reference) if color_reference is not None else None
    material_reference = image_pixels(material_reference) if material_reference is not None else None
    arrangement_reference = image_pixels(arrangement_reference) if arrangement_reference is not None else None
    job = OUTPUTS / datetime.now().strftime("job_%Y%m%d_%H%M%S_%f")
    job.mkdir(parents=True, exist_ok=True)
    source = job / "source.png"
    Image.fromarray(np.uint8(background)).save(source)
    source_for_seed = source
    lines = []
    if has_pose:
        source_mask_path = job / "source_mask.png"
        pose_path = job / "pose_reference.png"
        pose_mask_path = job / "pose_mask.png"
        pose_output = job / "pose_reconstructed.png"
        Image.fromarray(np.uint8(source_mask)).save(source_mask_path)
        Image.fromarray(np.uint8(pose_background)).save(pose_path)
        Image.fromarray(np.uint8(pose_mask)).save(pose_mask_path)
        pose_command = [
            sys.executable, str(ROOT / "run_pose_reference.py"), str(source),
            str(source_mask_path), str(pose_path), str(pose_mask_path), str(pose_output),
            "--identity-strength", str(pose_identity_strength),
            "--pose-strength", str(pose_structure_strength),
        ]
        lines.append("POSE STAGE: optional models install/download only on first use")
        yield [], "\n".join(lines), None
        pose_log = ROOT / "pose_reference.log"
        pose_process = subprocess.Popen(
            pose_command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        assert pose_process.stdout is not None
        with pose_log.open("w", encoding="utf-8") as log:
            for line in pose_process.stdout:
                log.write(line)
                log.flush()
                lines.append(line.rstrip())
                yield [], "\n".join(lines[-18:]), None
        if pose_process.wait():
            raise gr.Error(f"Pose reconstruction failed. Read {pose_log}")
        source_for_seed = pose_output
    amounts = {"Fidelity 15%": 0.15, "Balanced 28%": 0.28, "Detail 40%": 0.40}
    command = [sys.executable, str(ROOT / "run_seedvr2.py"), str(source_for_seed), "--scale", str(scale), "--no-explorer"]
    if mode == "Raw SeedVR2":
        command += ["--raw-output-only"]
    else:
        command += ["--fusion-amount", str(amounts[mode])]
        if save_raw:
            command += ["--save-raw"]
    if has_reference:
        lines.append(f"Reference mask coverage: {mask_coverage * 100:.1f}%")
        yield [], "\n".join(lines), None
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace")
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
    if has_pose:
        gallery.append((str(source_for_seed), "Experimental pose/layout reconstruction"))
    if raw:
        gallery.append((str(raw[-1]), "Raw SeedVR2"))
    if has_reference and mode != "Raw SeedVR2":
        feature_modes = {
            "自动分析（建议）": "auto",
            "表面细纹 / 颗粒 / 纤维": "microtexture",
            "光泽 / 哑光 / 柔和反射": "finish",
            "综合材质（不含颜色）": "material",
        }
        current = final
        applied = []
        stages = [
            ("color", color_reference, lambda src, ref, dst: apply_color_reference(
                src, ref, mask, dst, color_strength)),
            ("material", material_reference, lambda src, ref, dst: apply_reference(
                src, ref, mask, dst, material_strength, int(texture_size),
                feature_modes[material_feature])),
            ("arrangement", arrangement_reference, lambda src, ref, dst: apply_reference(
                src, ref, mask, dst, arrangement_strength, int(texture_size), "arrangement")),
        ]
        for stage_name, reference_pixels, operation in stages:
            if reference_pixels is None:
                continue
            stage_output = job / f"reference_stage_{stage_name}.png"
            try:
                report = operation(current, reference_pixels, stage_output)
                current = stage_output
                applied.append(stage_name)
                lines.append(
                    f"REFERENCE APPLIED [{stage_name}]: "
                    f"{report['masked_fraction'] * 100:.1f}% area"
                )
            except Exception as exc:
                lines.append(f"REFERENCE WARNING [{stage_name}]: {exc}; previous stage preserved")
        if applied:
            combined = job / f"source_ClearScale_MultiReference_{'-'.join(applied)}_{datetime.now():%Y%m%d_%H%M%S}.png"
            shutil.copy2(current, combined)
            final = combined
            gallery.append((str(final), f"Final references: {', '.join(applied)}"))
        else:
            gallery.append((str(final), "Fidelity result (all reference stages skipped)"))
    else:
        gallery.append((str(final), "Final"))
    yield gallery, "\n".join(lines[-18:]) + f"\nREADY: {final}", str(final)


def build_ui():
    css = """
    .gradio-container {max-width: 1600px !important; background:#15171b}
    .panel {border:1px solid #343841 !important; border-radius:12px !important; background:#1d2026 !important}
    """
    with gr.Blocks(title="ClearScale Material Studio", css=css, theme=gr.themes.Base()) as demo:
        gr.Markdown("# ClearScale Material Studio\n四个参考通道均可留空。姿态/摆放属于实验性生成阶段，首次使用会额外安装并下载模型；其他三个通道保持确定性处理。")
        with gr.Row():
            with gr.Column(scale=5, elem_classes="panel"):
                editor = gr.ImageEditor(label="1. 原图 — 使用参考材质时，涂满目标产品表面", type="numpy")
                with gr.Tabs():
                    with gr.Tab("颜色参考（可空）"):
                        color_reference = gr.ImageEditor(label="只参考颜色；目标明暗和细节保留", type="numpy")
                    with gr.Tab("材质参考（可空）"):
                        material_reference = gr.ImageEditor(label="参考颗粒、纤维、光泽或哑光", type="numpy")
                    with gr.Tab("排列参考（可空）"):
                        arrangement_reference = gr.ImageEditor(label="参考线距、织法和方向性排列", type="numpy")
                    with gr.Tab("姿态 / 摆放参考（实验，可空）"):
                        pose_reference = gr.ImageEditor(
                            label="参考整个产品的朝向、透视与构图；请涂满参考图中的目标产品区域",
                            type="numpy",
                        )
            with gr.Column(scale=3, elem_classes="panel"):
                mode = gr.Dropdown(["Fidelity 15%", "Balanced 28%", "Detail 40%", "Raw SeedVR2"], value="Balanced 28%", label="Detail mode")
                scale = gr.Radio([1.5, 2.0], value=2.0, label="Output scale")
                save_raw = gr.Checkbox(False, label="Also save raw SeedVR2 result")
                material_feature = gr.Dropdown(
                    ["自动分析（建议）", "表面细纹 / 颗粒 / 纤维",
                     "光泽 / 哑光 / 柔和反射", "综合材质（不含颜色）"],
                    value="自动分析（建议）", label="材质参考类型",
                )
                color_strength = gr.Slider(0.0, 1.0, value=0.65, step=0.05, label="颜色参考强度")
                material_strength = gr.Slider(0.0, 12.0, value=4.0, step=0.5, label="材质参考强度")
                arrangement_strength = gr.Slider(0.0, 12.0, value=4.0, step=0.5, label="排列参考强度")
                texture_size = gr.Slider(128, 640, value=320, step=32, label="材质 / 排列尺度")
                with gr.Accordion("实验性姿态 / 摆放参数", open=False):
                    pose_identity_strength = gr.Slider(0.3, 1.0, value=0.75, step=0.05, label="产品身份保持强度")
                    pose_structure_strength = gr.Slider(0.3, 1.2, value=0.90, step=0.05, label="姿态结构强度")
                    gr.Markdown("姿态阶段会重建画面，不能保证文字或细小孔位完全一致；建议先用无文字的产品图测试。")
                run = gr.Button("Enhance", variant="primary")
                status = gr.Textbox(label="Console", lines=18)
            with gr.Column(scale=5, elem_classes="panel"):
                gallery = gr.Gallery(label="3. 最终结果", columns=1, height=720, object_fit="contain")
                download = gr.File(label="下载最终 PNG（文件名会列出实际使用的参考通道）")
        run.click(process, [editor, color_reference, material_reference, arrangement_reference,
                            pose_reference, material_feature, mode, scale, save_raw, color_strength,
                            material_strength, arrangement_strength, texture_size,
                            pose_identity_strength, pose_structure_strength],
                  [gallery, status, download])
    return demo.queue(default_concurrency_limit=1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    app = build_ui()
    if not args.check:
        OUTPUTS.mkdir(exist_ok=True)
        app.launch(server_name="127.0.0.1", inbrowser=True, show_error=True)
