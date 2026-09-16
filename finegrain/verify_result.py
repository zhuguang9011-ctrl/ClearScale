"""Local evidence report. Metrics are diagnostics, never a material-quality score."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
from datetime import datetime, timezone
from PIL import Image, ImageOps
import numpy as np


def compare(source, result):
    with Image.open(source) as im:
        a = ImageOps.exif_transpose(im).convert('RGB')
    with Image.open(result) as im:
        im.verify()
    with Image.open(result) as im:
        b = ImageOps.exif_transpose(im).convert('RGB')
    aw, ah = a.size
    bw, bh = b.size
    x = np.asarray(a, dtype=np.float32)
    y = np.asarray(b.resize(a.size, Image.Resampling.LANCZOS), dtype=np.float32)
    delta = y - x
    baseline = np.asarray(a.resize(b.size, Image.Resampling.LANCZOS), dtype=np.float32)
    output = np.asarray(b, dtype=np.float32)
    non_interpolation_delta = output - baseline
    source_luma = x @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    result_luma = y @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    source_edges = np.hypot(*np.gradient(source_luma))
    result_edges = np.hypot(*np.gradient(result_luma))
    edge_correlation = float(np.corrcoef(source_edges.ravel(), result_edges.ravel())[0, 1])
    return {
        'input_size': [aw, ah], 'output_size': [bw, bh],
        'scale_xy': [bw / aw, bh / ah],
        'aspect_ratio_relative_error': abs((bw / bh) / (aw / ah) - 1),
        'mean_absolute_rgb_change_0_255': float(np.abs(delta).mean()),
        'mean_signed_rgb_change_0_255': delta.mean(axis=(0, 1)).tolist(),
        'change_beyond_lanczos_mae_0_255': float(np.abs(non_interpolation_delta).mean()),
        'edge_map_correlation': edge_correlation,
        'warning': 'Compare only matching crops. Color/shape/material fidelity requires visual inspection; low pixel difference does not prove quality.'
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('result')
    args = parser.parse_args()
    report = {'time_utc': datetime.now(timezone.utc).isoformat(), 'platform': platform.platform(),
              'scope': 'Existing output decoding and same-crop comparison; GPU arithmetic smoke test, NOT model inference or a material-quality score.'}
    try:
        import torch
        report['torch'] = torch.__version__
        report['cuda_available'] = torch.cuda.is_available()
        if torch.cuda.is_available():
            report['gpu'] = torch.cuda.get_device_name(0)
            report['vram_bytes'] = torch.cuda.get_device_properties(0).total_memory
            x = torch.ones((128, 128), device='cuda')
            value = (x @ x)[0, 0].item()
            report['gpu_arithmetic_pass'] = value == 128
    except Exception as exc:
        report['gpu_error'] = str(exc)
    try:
        report['comparison'] = compare(args.source, args.result)
        report['output_sha256'] = hashlib.sha256(Path(args.result).read_bytes()).hexdigest()
        report['output_decode_pass'] = True
    except Exception as exc:
        report['output_decode_pass'] = False
        report['image_error'] = str(exc)
    folder = Path(__file__).resolve().parent / 'verification_reports'
    folder.mkdir(exist_ok=True)
    path = folder / ('report_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json')
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print('Report:', path)
    return 0 if report['output_decode_pass'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
