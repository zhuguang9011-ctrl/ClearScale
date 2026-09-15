"""Install pinned upstream into a private runtime. No model downloads at this stage."""
import argparse
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REVISION = 'a632fb6b948fa6b1a55d816982655d6dc8ed995e'
REFINERS = 'a5d3c2971b84f6faa4762b1cf5a07f4f812bb1f5'
VERSION = 'launcher-0.1.0'

def patch_app(text):
    replacements = {
        'loras_scale={"more_details": 0.5, "sdxl_render": 1.0}': 'loras_scale={"more_details": 0.0, "sdxl_render": 0.0}',
        'value=112,': 'value=64,',
        'value=144,': 'value=64,',
        'run_button = gr.ClearButton(': 'run_button = gr.Button(',
        '                        components=None,\n': '',
        '                    run_button.add(output_slider)\n': '',
        'demo.launch(share=False)': 'demo.launch(share=False, server_name="127.0.0.1", inbrowser=True)',
    }
    for old, new in replacements.items():
        if old not in text:
            raise RuntimeError('Upstream changed; patch stopped: ' + old)
        text = text.replace(old, new)
    return '# Modified by ClearScale: conservative defaults, regular run button, local-only browser launch.\n' + text

def install(uv):
    runtime = ROOT / 'runtime'
    runtime.mkdir(exist_ok=True)
    marker = runtime / 'installed.json'
    if marker.exists() and json.loads(marker.read_text()).get('version') == VERSION:
        print('Dependencies already installed. Checking application next.', flush=True)
        return
    archive = runtime / 'upstream.zip'
    print('Downloading pinned Finegrain source...', flush=True)
    urllib.request.urlretrieve(f'https://github.com/pinokiofactory/clarity-refiners-ui/archive/{REVISION}.zip', archive)
    unpack = runtime / 'unpack'
    unpack.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            dest = (unpack / item.filename).resolve()
            if not dest.is_relative_to(unpack.resolve()):
                raise RuntimeError('Invalid archive path')
        z.extractall(unpack)
    source = runtime / 'source'
    extracted = unpack / f'clarity-refiners-ui-{REVISION}'
    shutil.copytree(extracted, source, dirs_exist_ok=True)
    app = source / 'app'
    original = (app / 'app.py').read_text(encoding='utf-8')
    (app / 'app.upstream.py').write_text(original, encoding='utf-8')
    (app / 'app.py').write_text(patch_app(original), encoding='utf-8')
    requirements = (app / 'requirements.txt').read_text(encoding='utf-8')
    requirements = requirements.replace(f'git+https://github.com/finegrain-ai/refiners@{REFINERS}', f'https://github.com/finegrain-ai/refiners/archive/{REFINERS}.zip')
    requirements += '\npsutil\npydantic>=2.0,<2.11.0\nhuggingface-hub<1\n'
    (runtime / 'requirements.txt').write_text(requirements, encoding='utf-8')
    constraints = runtime / 'constraints.txt'
    constraints.write_text('torch==2.7.0\ntorchvision==0.22.0\ntorchaudio==2.7.0\n', encoding='utf-8')
    def pip(*args):
        subprocess.run([uv, 'pip', 'install', '--python', sys.executable, *args], check=True)
    print('Installing PyTorch CUDA 12.8...', flush=True)
    pip('torch==2.7.0', 'torchvision==0.22.0', 'torchaudio==2.7.0', '--index-url', 'https://download.pytorch.org/whl/cu128')
    print('Installing Finegrain dependencies...', flush=True)
    pip('-r', str(runtime / 'requirements.txt'), '-c', str(constraints))
    subprocess.run([uv, 'pip', 'check', '--python', sys.executable], check=True)
    marker.write_text(json.dumps({'version': VERSION, 'upstream': REVISION}), encoding='utf-8')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--uv', required=True)
    install(parser.parse_args().uv)
