"""Build the real UI while omitting model initialization. This is NOT an inference test."""
import ast
import os
import sys
from pathlib import Path
from unittest.mock import patch

app = Path(__file__).resolve().parent / 'runtime' / 'source' / 'app'
os.chdir(app)
sys.path.insert(0, str(app))
tree = ast.parse((app / 'app.py').read_text(encoding='utf-8'))
tree.body = [node for node in tree.body if not (
    isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {'CHECKPOINTS', 'device', 'dtype', 'enhancer'} for t in node.targets)
)]
import gradio
with patch.object(gradio.Blocks, 'launch'), patch('huggingface_hub.hf_hub_download', side_effect=AssertionError('Smoke test must not download models')):
    namespace = {'__name__': '__main__', '__file__': str(app / 'app.py')}
    exec(compile(tree, str(app / 'app.py'), 'exec'), namespace)
    assert namespace['demo'].config['components']
    namespace['demo'].close()
print('PASS: dependency imports and real Gradio UI construction. GPU/model inference NOT tested.')
