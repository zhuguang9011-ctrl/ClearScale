"""Start bundled upstream applications; retain errors in logs."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
def main():
    roaming=ROOT/'profile/Roaming'
    local=ROOT/'profile/Local'
    for p in (roaming/'krita',local,ROOT/'logs',ROOT/'outputs'): p.mkdir(parents=True,exist_ok=True)
    dest=roaming/'krita/pykrita'
    if not (dest/'ai_diffusion').exists(): shutil.copytree(ROOT/'plugin',dest,dirs_exist_ok=True)
    # Isolated profile; never overwrite an existing Krita user's settings.
    for folder in (roaming,local):
        rc=folder/'kritarc'
        if not rc.exists(): rc.write_text('[python]\nenable_ai_diffusion=true\n',encoding='utf-8')
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
    config={'server_mode':'external','server_url':f'127.0.0.1:{port}','performance_preset':'low','auto_update':False,'language':'zh_CN','apply_behavior':'layer'}
    for p in (roaming/'krita/ai_diffusion/settings.json',roaming/'krita-ai-diffusion/settings.json'):
        p.parent.mkdir(parents=True,exist_ok=True)
        existing=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        existing.update({k:v for k,v in config.items() if k not in existing or k in ('server_mode','server_url')})
        p.write_text(json.dumps(existing),encoding='utf-8')
    env=dict(os.environ,APPDATA=str(roaming),LOCALAPPDATA=str(local))
    log=(ROOT/'logs/backend.log').open('w',encoding='utf-8')
    server=subprocess.Popen([str(ROOT/'python/python.exe'),'-s',str(ROOT/'ComfyUI/main.py'),'--listen','127.0.0.1','--port',str(port),'--lowvram','--output-directory',str(ROOT/'outputs')],cwd=ROOT/'ComfyUI',env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        print('Starting ComfyUI. Log: logs/backend.log',flush=True)
        for i in range(180):
            if server.poll() is not None: raise RuntimeError('Backend failed. See logs/backend.log')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/system_stats',timeout=2) as r: json.load(r)
                break
            except Exception: time.sleep(2)
        else: raise RuntimeError('Startup timed out. See logs/backend.log')
        print('Backend ready. Open Settings > Dockers > AI Image Generation in Krita.',flush=True)
        print('Close Krita to stop this bundled backend.',flush=True)
        subprocess.run([str(ROOT/'krita/bin/krita.exe'),'--nosplash'],env=env,check=True)
    finally:
        server.terminate()
        server.wait(timeout=30)
        log.close()

if __name__=='__main__':
    try: main()
    except Exception as e:
        print('ERROR:',e,flush=True)
        raise SystemExit(1)
