"""Exercise real Gradio output serialization/cache handling with fake inference only."""
import asyncio
import ast
import tempfile
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import gradio as gr
from PIL import Image
from bootstrap import patch_app

source = Path(__file__).resolve().parent / 'runtime' / 'source' / 'app' / 'app.upstream.py'
tree = ast.parse(patch_app(source.read_text(encoding='utf-8')))
# Execute the actual result wrapper and native output component from patched upstream.
wrapper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'process_and_update')
component = next(node for node in ast.walk(tree) if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'output_slider' for t in node.targets))
async def main():
    with tempfile.TemporaryDirectory() as folder:
        original = Image.new('RGBA', (33, 47), (20, 100, 150, 128))
        enhanced = original.resize((66, 94))
        saved = Path(folder) / 'result.png'
        enhanced.save(saved)
        ns = {'gr': gr, 'Image': Image, 'List': list, 'process': lambda *args: (original, enhanced), 'update_gallery': lambda: [str(saved)]}
        exec(compile(ast.Module(body=[wrapper], type_ignores=[]), '<upstream-wrapper>', 'exec'), ns)
        with gr.Blocks() as demo:
            exec(compile(ast.Module(body=[component], type_ignores=[]), '<upstream-component>', 'exec'), ns)
            recent = gr.Gallery()
            button = gr.Button()
            button.click(ns['process_and_update'], inputs=[], outputs=[ns['output_slider'], recent])
        # Covers processing_utils async file-cache path rewriting, not just postprocess().
        output = await demo.process_api(0, inputs=[], state=None, simple_format=False)
        images = output['data'][0]
        assert len(images) == 2
        for data, expected in zip(images, [(33, 47), (66, 94)]):
            path = Path(data['image']['path'])
            assert path.is_file()
            with Image.open(path) as im:
                assert im.size == expected
                assert im.mode == 'RGBA'
                assert im.getpixel((0, 0))[3] == 128
        assert Path(output['data'][1][0]['image']['path']).is_file()
        assert len(saved.read_bytes()) > 0
        process_node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'process')
        noop = lambda *a, **k: None
        ns.update(message_manager=SimpleNamespace(add_warning=noop, add_error=noop), gc=SimpleNamespace(collect=noop), devicetorch=SimpleNamespace(empty_cache=noop), torch=None)
        exec(compile(ast.Module(body=[process_node], type_ignores=[]), '<upstream-process>', 'exec'), ns)
        try:
            ns['process'](None)
        except gr.Error as error:
            assert 'Please load an image first' in str(error)
        else:
            raise AssertionError('Failure must raise a visible error, not return an empty result')
        demo.close()
    print('PASS: actual wrapper -> native gallery -> Gradio API cache; PNG dimensions and alpha preserved. No model inference.')

asyncio.run(main())
