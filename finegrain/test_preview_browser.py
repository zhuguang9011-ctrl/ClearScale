"""Optional browser regression; install playwright and Chromium first. No AI inference."""
import ast
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import gradio as gr
from PIL import Image
from playwright.sync_api import sync_playwright
from bootstrap import patch_app

os.environ['NO_PROXY'] = os.environ.get('NO_PROXY', '') + ',localhost,127.0.0.1'
source = Path(__file__).resolve().parent / 'runtime/source/app/app.upstream.py'
tree = ast.parse(patch_app(source.read_text(encoding='utf-8')))
wrapper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'process_and_update')
component = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'output_slider' for t in n.targets))
with TemporaryDirectory() as folder:
    original = Image.new('RGBA', (33, 47), (20, 100, 150, 128))
    enhanced = original.resize((66, 94))
    saved = Path(folder) / 'saved.png'
    enhanced.save(saved)
    ns = {'gr': gr, 'process': lambda *args: (original, enhanced), 'update_gallery': lambda: [str(saved)]}
    exec(compile(ast.Module(body=[wrapper], type_ignores=[]), '<upstream-wrapper>', 'exec'), ns)
    with gr.Blocks() as demo:
        exec(compile(ast.Module(body=[component], type_ignores=[]), '<upstream-component>', 'exec'), ns)
        ns['output_slider'].elem_id = 'result'
        recent = gr.Gallery()
        button = gr.Button('Preview test')
        button.click(ns['process_and_update'], inputs=[], outputs=[ns['output_slider'], recent])
    try:
        _, url, _ = demo.launch(server_name='127.0.0.1', prevent_thread_lock=True, share=False, quiet=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, channel=os.environ.get('CLEARSCALE_BROWSER_CHANNEL'))
            page = browser.new_page()
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(url)
            page.get_by_role('button', name='Preview test', exact=True).click()
            page.wait_for_function("""() => {
              const images = [...document.querySelectorAll('#result img')];
              return images.some(i => i.naturalWidth === 33) && images.some(i => i.naturalWidth === 66);
            }""", timeout=30000)
            assert not errors, errors
            browser.close()
        print('PASS: Chromium clicked actual result wrapper; both PNG previews loaded. No model inference.')
    finally:
        demo.close()
