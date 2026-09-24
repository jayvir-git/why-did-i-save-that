"""Repeatable setup. Default: standard-library checks/demo/config, no downloads or login."""
import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'scripts'))
from demo import demo


def write_config(path, workspace):
    value = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    entry = {'command':sys.executable,'args':[str(ROOT/'scripts/workspace.py'),'--workspace',str(workspace),'mcp']}
    servers = value.setdefault('mcpServers',{})
    if 'gold-workspace' in servers and servers['gold-workspace']!=entry:
        raise ValueError('gold-workspace already has different settings in '+str(path)+'. Choose another --mcp-output or reconcile that entry.')
    servers['gold-workspace']=entry
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def setup(args):
    if sys.version_info < (3,12): raise RuntimeError('Python 3.12+ is required; rerun with a supported interpreter.')
    sys.path.insert(0,str(ROOT/'.runtime'))
    workspace = pathlib.Path(args.workspace).resolve()
    workspace.mkdir(parents=True,exist_ok=True)
    selected = set(args.features)
    receipt_path = workspace/'setup-receipt.json'
    previous = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    # Install only explicitly requested capabilities; retries never import personal sources.
    for feature in sorted(selected):
        if feature in ('semantic','extraction'):
            requirements = ROOT/('requirements-enrichment.txt' if feature=='extraction' else 'requirements-workspace.txt')
            signature = hashlib.sha256(requirements.read_bytes()+(ROOT/'requirements-workspace.txt').read_bytes()+sys.version.encode()).hexdigest()
            modules = ['onnxruntime','tokenizers','numpy'] + (['rapidocr','PIL','pypdf','trafilatura'] if feature=='extraction' else [])
            if args.reinstall or previous.get(feature)!=signature or not all(importlib.util.find_spec(x) for x in modules):
                subprocess.run([sys.executable,'-m','pip','install','--upgrade','--target',str(ROOT/'.runtime'),'-r',str(requirements)],cwd=ROOT,check=True,stdout=sys.stderr)
                previous[feature]=signature
        if feature in ('semantic','extension'):
            assets = ['extension/models/Xenova/all-MiniLM-L6-v2/onnx/model_quantized.onnx','extension/models/Xenova/all-MiniLM-L6-v2/tokenizer.json','extension/vendor/transformers.min.js','extension/vendor/ort-wasm.wasm','extension/vendor/ort-wasm-simd.wasm']
            if not all((ROOT/x).is_file() for x in assets):
                subprocess.run([sys.executable,str(ROOT/'scripts/fetch-model.py')],cwd=ROOT,check=True,stdout=sys.stderr)
    verified = {}
    if selected & {'semantic','extraction'}:
        probe = 'import sys;sys.path[:0]=sys.argv[1:3];'
        if 'semantic' in selected:
            probe += 'from gold_workspace.semantic import embed;v=embed(["Synthetic setup check"]);assert len(v)==1 and len(v[0])==384;'
            verified['semantic']='local model produced a 384-dimensional embedding of synthetic text'
        if 'extraction' in selected:
            probe += 'import rapidocr,PIL,pypdf,trafilatura;'
            verified['extraction']='dependencies imported; remote capture and OCR model initialization not exercised'
        subprocess.run([sys.executable,'-I','-c',probe,str(ROOT),str(ROOT/'.runtime')],cwd=ROOT,check=True,stdout=sys.stderr,timeout=120)
    report = demo()
    from gold_workspace import Workspace
    w=Workspace(workspace)
    try: posts=w.inventory()['posts']
    finally:w.close()
    output=pathlib.Path(args.mcp_output).resolve() if args.mcp_output else workspace/'mcp.json'
    write_config(output,workspace)
    providers={name:{'installed':bool(shutil.which(os.environ.get('GOLD_'+name.upper()+'_BIN') or name)),
                     'authentication':'not checked; sign in through the provider CLI'} for name in ('codex','claude')}
    previous['python']=sys.version.split()[0]
    receipt_path.write_text(json.dumps(previous,indent=2),encoding='utf-8')
    return {'status':'ready','workspace':str(workspace),'posts':posts,'demo':report,'mcp_config':str(output),'providers':providers,
            'requested_features':sorted(selected),'verified_optional_capabilities':verified,
            'app_command':[sys.executable,str(ROOT/'scripts/workspace.py'),'--workspace',str(workspace),'app'],'next_steps':[
                'Start the app using the app_command argument list above (quote paths containing spaces in a shell).',
                'For Claude Code: claude --mcp-config "'+str(output)+'" (approve this local server when prompted).',
                'For other MCP clients: import the generated mcpServers entry. CLI agents can use scripts/workspace.py directly.',
                'Import your exported collection or load/pair the Chrome extension. Setup does not sign in or collect personal data.',
                'After importing/extracting evidence, build the optional meaning index using index_attachments.']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',default=str(ROOT/'workspace-data'))
    parser.add_argument('--with',dest='features',action='append',choices=['semantic','extraction','extension'],default=[])
    parser.add_argument('--reinstall',action='store_true',help='Reinstall dependencies for the selected --with capabilities')
    parser.add_argument('--mcp-output',help='Merge the server entry into this JSON file; conflicting entries are preserved and reported')
    try: print(json.dumps(setup(parser.parse_args()),indent=2))
    except Exception as error:
        print(json.dumps({'status':'blocked','error':str(error),'next_step':'Resolve the reported prerequisite and rerun the same setup command.'}));sys.exit(1)
