"""Read-only installation checks; never prints tokens or library contents."""
import importlib.util
import json
import pathlib
import shutil
import sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'.runtime'))
checks={'python':sys.version.split()[0], 'node':bool(shutil.which('node')), 'local_model':(ROOT/'extension/models/Xenova/all-MiniLM-L6-v2/onnx/model_quantized.onnx').exists(), 'semantic_runtime':all(importlib.util.find_spec(x) for x in ['numpy','onnxruntime','tokenizers']), 'database':(ROOT/'workspace-data/workspace.sqlite').exists(), 'attachment_index':(ROOT/'workspace-data/attachment-search-latest.json').exists()}
print(json.dumps(checks,indent=2))
