"""Assemble unmodified upstream applications on Windows. No image algorithms."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
OUT = HERE / 'dist' / 'Product-Editor-Full'
CACHE = HERE / 'downloads'
OUT.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(exist_ok=True)
records = []

def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def fetch(url, target, expected=None):
    target.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            print('Downloading:', url, flush=True)
            req = urllib.request.Request(url, headers={'User-Agent':'ProductEditor-Assembly/1.0'})
            with urllib.request.urlopen(req, timeout=90) as src, target.with_suffix('.part').open('wb') as dst:
                shutil.copyfileobj(src, dst, 4*1024*1024)
            target.with_suffix('.part').replace(target)
            sha = digest(target)
            if expected and sha != expected:
                raise RuntimeError('SHA256 mismatch: '+target.name)
            records.append({'url':url,'file':str(target.relative_to(HERE)), 'sha256':sha, 'bytes':target.stat().st_size})
            return target
        except Exception:
            if attempt == 2: raise
            time.sleep(2)

def extract(archive, dest, strip=False):
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            parts = Path(info.filename).parts
            if strip: parts = parts[1:]
            if not parts: continue
            target = dest.joinpath(*parts).resolve()
            if not target.is_relative_to(dest.resolve()): raise ValueError('Invalid archive path')
            if info.is_dir(): target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, target.open('wb') as dst: shutil.copyfileobj(src,dst)

def repo(url, revision, target):
    archive = fetch(url+'/archive/'+revision+'.zip', OUT/'sources'/(target.name+'-'+revision+'.zip'))
    extract(archive,target,strip=True)

def run(args, **kw):
    subprocess.run([str(x) for x in args],check=True,**kw)

assert sys.platform == 'win32', 'Build on Windows only'
plugin = fetch('https://github.com/Acly/krita-ai-diffusion/releases/download/v1.53.0/krita_ai_diffusion-1.53.0.zip',CACHE/'plugin.zip','05b4e4072faecbcfa441a8829c97492cfe35974c92e407d0197db4e78ec91cbe')
extract(plugin,OUT/'plugin')
repo('https://github.com/Acly/krita-ai-diffusion','v1.53.0',CACHE/'plugin-source')
krita = fetch('https://download.kde.org/stable/krita/5.3.2.1/krita-x64-5.3.2.1.zip',CACHE/'krita.zip')
extract(krita,OUT/'krita',strip=True)
assert (OUT/'krita/bin/krita.exe').exists()
# KDE publishes shared sources for the Qt5 and Qt6 builds under 6.0.2.1.
fetch('https://download.kde.org/stable/krita/6.0.2.1/krita-6.0.2.1.tar.xz',OUT/'sources/krita-6.0.2.1.tar.xz')
py = fetch('https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip',CACHE/'python.zip')
extract(py,OUT/'python')
(OUT/'python/python312._pth').write_text('python312.zip\n.\nLib/site-packages\n../ComfyUI\nimport site\n')
python = OUT/'python/python.exe'
uvzip = fetch('https://github.com/astral-sh/uv/releases/download/0.9.26/uv-x86_64-pc-windows-msvc.zip',CACHE/'uv.zip')
extract(uvzip,CACHE/'uv')
uv = next((CACHE/'uv').rglob('uv.exe'))
comfy = OUT/'ComfyUI'
repo('https://github.com/comfyanonymous/ComfyUI','4da9e2dbead52fc1e68beae33fe3d7ad63b63241',comfy)
nodes = [
 ('https://github.com/Fannovel16/comfyui_controlnet_aux','e8b689a513c3e6b63edc44066560ca5919c0576e','comfyui_controlnet_aux'),
 ('https://github.com/cubiq/ComfyUI_IPAdapter_plus','b188a6cb39b512a9c6da7235b880af42c78ccd0d','ComfyUI_IPAdapter_plus'),
 ('https://github.com/Acly/comfyui-tooling-nodes','ca01116495cad1f2d8440641f26ced8fbdbbe8de','comfyui-tooling-nodes'),
 ('https://github.com/Acly/comfyui-inpaint-nodes','12937559e1aea4bb073e9e82f915d1dab92f248b','comfyui-inpaint-nodes'),
]
for url,rev,name in nodes: repo(url,rev,comfy/'custom_nodes'/name)
env = dict(os.environ, UV_CACHE_DIR=str(CACHE/'uv-cache'))
req = CACHE/'plugin-source/ai_diffusion/backend/requirements/windows-cuda.txt'
run([uv,'pip','install','--python',python,'--index-strategy','unsafe-best-match','-r',req],env=env)
run([uv,'pip','install','--python',python,'-r',comfy/'requirements.txt'],env=env)
run([python,'-c','import torch, torchvision, aiohttp, safetensors; print(torch.__version__)'])
with (OUT/'installed-packages.txt').open('w') as f:
    run([uv,'pip','freeze','--python',python],stdout=f)

for model in json.loads((HERE/'models.json').read_text()):
    for entry in model['files']: fetch(entry['url'],comfy/entry['path'],entry.get('sha256'))
shutil.copy2(HERE/'models.json',OUT/'models-manifest.json')
for name in ('launch.py','START.cmd','FIX-AI-PLUGIN.cmd','使用说明.txt'): shutil.copy2(HERE/name,OUT/name)
shutil.copy2(HERE.parent/'THIRD-PARTY-LICENSE.txt',OUT/'PLUGIN-LICENSE.txt')
# Preserve model cards alongside unmodified model weights.
for slug in ['SG161222/RealVisXL_V5.0','h94/IP-Adapter','ByteDance/Hyper-SD','lllyasviel/fooocus_inpaint','Acly/Omni-SR']:
    fetch('https://huggingface.co/'+slug+'/raw/main/README.md',OUT/'licenses'/(slug.replace('/','-')+'-README.md'))
fetch('https://raw.githubusercontent.com/advimman/lama/main/LICENSE',OUT/'licenses/LaMa-LICENSE.txt')

# Actual backend smoke test on Windows CPU: validates imports and node/model discovery, not GPU generation.
logfile = (OUT/'build-backend.log').open('w',encoding='utf-8')
proc = subprocess.Popen([str(python),'-s',str(comfy/'main.py'),'--cpu','--listen','127.0.0.1','--port','8199'],cwd=comfy,stdout=logfile,stderr=subprocess.STDOUT)
try:
    for i in range(180):
        if proc.poll() is not None: raise RuntimeError('Backend exited; see build-backend.log')
        try:
            with urllib.request.urlopen('http://127.0.0.1:8199/object_info',timeout=3) as r: info=json.load(r)
            break
        except Exception: time.sleep(2)
    else: raise RuntimeError('Backend startup timeout')
    for node in ['IPAdapter','ETN_LoadImageCache','ETN_SaveImageCache','INPAINT_LoadFooocusInpaint','INPAINT_LoadInpaintModel','InpaintPreprocessor']:
        assert node in info, 'Missing node: '+node
    checkpoints=info['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
    assert 'RealVisXL_V5.0_fp16.safetensors' in checkpoints
    (OUT/'validation.json').write_text(json.dumps({'windows_backend_startup':True,'required_nodes':True,'checkpoint_discovery':True,'gpu_inference_tested':False,'krita_gui_tested':False},indent=2))
finally:
    proc.terminate()
    proc.wait(timeout=30)
    logfile.close()
(OUT/'download-manifest.json').write_text(json.dumps(records,indent=2))
print('Full assembly and Windows backend smoke test passed. GPU image quality NOT tested.',flush=True)
