"""Exercise import, search, exact citations, replay and MCP in a disposable archive."""
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def demo():
    with tempfile.TemporaryDirectory(prefix='inator-demo-') as folder:
        base = [sys.executable, '-I', str(ROOT/'scripts/workspace.py'), '--workspace', folder]
        def call(operation, arguments=None):
            args = pathlib.Path(folder)/'args.json'
            args.write_text(json.dumps(arguments or {}), encoding='utf-8')
            result = subprocess.run(base+[operation, '--args-file', str(args)], capture_output=True, text=True, encoding='utf-8', timeout=30)
            if result.returncode: raise RuntimeError(result.stderr or result.stdout)
            return json.loads(result.stdout)
        text = 'Spaced retrieval helps retain what you learn.'
        post = {'key':'demo:123456','id':'123456','owner':'demo','author':'example','text':text,
                'sources':['bookmarks'],'url':'https://example.com/123456','links':[],'media':[]}
        call('import_backup', {'data':{'format':'gold-collector','version':1,'posts':[post]}})
        found = call('search_library', {'text':'spaced retrieval','mode':'keyword'})
        rows = call('result', {'result_id':found['receipt']['result_id']})['rows']
        if len(rows)!=1: raise RuntimeError('Demo search did not return its source')
        evidence = {'observation_id':rows[0]['observation_id'],'field':'text','start':0,'end':len(text),'quote':text}
        args = {'client_request_id':'demo-cited-note','title':'Retrieval practice','text':'Try spaced retrieval.', 'evidence':[evidence]}
        saved = call('save_note',args)
        if call('save_note',args)!=saved: raise RuntimeError('Replay created another note')
        artifact = call('read_artifact',{'investigation_id':saved['investigation_id'],'name':saved['name']})
        if artifact['content']['evidence'] != [evidence]: raise RuntimeError('Citation was not persisted')
        requests = [{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'demo','version':'1'}}},
                    {'jsonrpc':'2.0','method':'notifications/initialized'},
                    {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                    {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'inventory','arguments':{}}}]
        proc = subprocess.run(base+['mcp'], input=''.join(json.dumps(x)+'\n' for x in requests),capture_output=True,text=True,encoding='utf-8',timeout=30)
        replies = [json.loads(x) for x in proc.stdout.splitlines()]
        if proc.returncode or len(replies)!=3 or any('error' in x for x in replies): raise RuntimeError('MCP handshake failed')
        tools = replies[1]['result']['tools']
        if not any(x['name']=='save_note' for x in tools): raise RuntimeError('MCP catalog incomplete')
        result = replies[2]['result']
        if result.get('isError') or json.loads(result['content'][0]['text'])['posts']!=1: raise RuntimeError('MCP inventory failed')
        return {'status':'passed','checks':['import','keyword search','cited note','idempotent replay','persistence across processes','MCP initialize/list/call'],
                'workspace':'disposable synthetic archive; removed after run','provider_calls':0}


if __name__=='__main__':
    try: print(json.dumps(demo(),indent=2))
    except Exception as error:
        print(json.dumps({'status':'failed','error':str(error)}));sys.exit(1)
