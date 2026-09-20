"""Fetch pinned public inference assets; never reads the user's library."""
import base64, hashlib, io, json, pathlib, tarfile, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1] / 'extension'
def get(url):
    with urllib.request.urlopen(url, timeout=180) as response:
        return response.read()
def write(path, data):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    print(path, len(data), flush=True)

meta = json.loads(get('https://registry.npmjs.org/@xenova/transformers/2.17.2'))
archive = get(meta['dist']['tarball'])
assert 'sha512-' + base64.b64encode(hashlib.sha512(archive).digest()).decode() == meta['dist']['integrity']
with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as package:
    for name in ['transformers.min.js', 'ort-wasm-simd.wasm', 'ort-wasm.wasm']:
        write('vendor/' + name, package.extractfile('package/dist/' + name).read())
    write('vendor/TRANSFORMERS-LICENSE', package.extractfile('package/LICENSE').read())
for name in ['LICENSE', 'ThirdPartyNotices.txt']:
    write('vendor/ONNX-' + name, get('https://raw.githubusercontent.com/microsoft/onnxruntime/v1.14.0/' + name))

model = 'Xenova/all-MiniLM-L6-v2'
revision = '751bff37182d3f1213fa05d7196b954e230abad9'
for name in ['config.json', 'tokenizer.json', 'tokenizer_config.json', 'onnx/model_quantized.onnx']:
    write('models/' + model + '/' + name, get(f'https://huggingface.co/{model}/resolve/{revision}/{name}'))
write('models/provenance.json', json.dumps({'model':model, 'revision':revision, 'runtime':'@xenova/transformers@2.17.2'}, indent=2).encode())
