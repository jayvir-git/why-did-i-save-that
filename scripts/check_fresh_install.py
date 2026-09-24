"""Offline baseline acceptance in a clean copy, from an unrelated working directory."""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT=pathlib.Path(__file__).resolve().parents[1]


def check():
    with tempfile.TemporaryDirectory(prefix='inator-fresh-') as folder:
        folder=pathlib.Path(folder); checkout=folder/'clean checkout'; checkout.mkdir()
        shutil.copytree(ROOT/'gold_workspace',checkout/'gold_workspace',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        (checkout/'scripts').mkdir()
        for name in ['setup.py','demo.py','workspace.py','fetch-model.py']:
            shutil.copy2(ROOT/'scripts'/name,checkout/'scripts'/name)
        for name in ['requirements-workspace.txt','requirements-enrichment.txt']:
            shutil.copy2(ROOT/name,checkout/name)
        command=[sys.executable,'-I',str(checkout/'scripts/setup.py')]
        for attempt in range(2):
            proc=subprocess.run(command,cwd=folder,capture_output=True,text=True,encoding='utf-8',timeout=90)
            if proc.returncode: raise RuntimeError(proc.stderr or proc.stdout)
            report=json.loads(proc.stdout)
            if report['status']!='ready' or report['posts']!=0 or report['demo']['status']!='passed': raise RuntimeError('Baseline acceptance failed')
        config=json.loads(pathlib.Path(report['mcp_config']).read_text())['mcpServers']['gold-workspace']
        proc=subprocess.run([config['command'],*config['args']],cwd=folder,input='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"inventory","arguments":{}}}\n',capture_output=True,text=True,encoding='utf-8',timeout=30)
        response=json.loads(proc.stdout)['result']
        if proc.returncode or response.get('isError') or json.loads(response['content'][0]['text'])['posts']!=0: raise RuntimeError('Generated MCP configuration failed')
        if (checkout/'.runtime').exists() or (checkout/'extension').exists(): raise RuntimeError('Baseline installed optional assets')
        return {'status':'passed','checks':['clean copy without dependencies/models/private archive','setup twice','unrelated working directory','generated MCP config','no optional downloads']}


if __name__=='__main__':
    try:print(json.dumps(check(),indent=2))
    except Exception as error:print(json.dumps({'status':'failed','error':str(error)}));sys.exit(1)
