"""Repeatable HTTP + first-page latency / labelled retrieval benchmark.

Uses a disposable synthetic corpus by default. Cold samples each start a fresh
server process; warm samples reuse it. Does not claim real-library relevance.
"""
import argparse
import json
import math
import multiprocessing
import pathlib
import statistics
import sys
import tempfile
import time
import urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gold_workspace import Workspace

CASES=[('database indexing','SQLite database indexing improves selective query plans.'),
       ('study retrieval practice','Study with retrieval practice and spaced repetition.'),
       ('accessible keyboard navigation','Accessible keyboard navigation and visible focus for websites.'),
       ('sourdough fermentation','Sourdough fermentation starter temperature and baking.'),
       ('transcript timecodes','Transcript timecodes identify spoken content in video.'),
       ('portfolio typography','Portfolio typography spacing and readable headings.')]

def serve(path,pipe):
    from gold_workspace.app import server
    app=server(path,0);pipe.send(app.server_port);pipe.close()
    app.serve_forever()

def request(port,operation,args):
    origin=f'http://127.0.0.1:{port}'
    req=urllib.request.Request(origin+'/api',json.dumps({'operation':operation,'args':args}).encode(),headers={'Content-Type':'application/json','Origin':origin})
    with urllib.request.urlopen(req,timeout=90) as response:return json.load(response)

def sample(port,query,expected,mode):
    start=time.perf_counter();result=request(port,'search_library',{'text':query,'mode':mode})
    page=request(port,'result',{'result_id':result['receipt']['result_id'],'limit':20})
    return {'query':query,'ms':round((time.perf_counter()-start)*1000,2),'hit_at_5':expected in [r['observation_id'] for r in page['rows'][:5]],'fallback':result['receipt'].get('fallback')}

def summary(samples):
    values=sorted(s['ms'] for s in samples)
    return {'samples':len(values),'p50_ms':round(statistics.median(values),2),'p95_ms':values[math.ceil(.95*len(values))-1],'expected_source_hit_at_5':sum(s['hit_at_5'] for s in samples)/len(samples)}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--posts',type=int,default=1200);parser.add_argument('--output');parser.add_argument('--mode',choices=['keyword','hybrid','semantic'],default='keyword');parser.add_argument('--warm-budget-ms',type=float,default=500);parser.add_argument('--cold-budget-ms',type=float,default=2500);args=parser.parse_args()
    if args.posts<len(CASES):parser.error('--posts must be at least 6')
    with tempfile.TemporaryDirectory(prefix='inator-search-benchmark-') as folder:
        w=Workspace(folder);posts=[]
        for i in range(args.posts):
            text=CASES[i][1] if i<len(CASES) else ('Archived miscellaneous entry number '+str(i)+' with unrelated everyday observations. ')*8
            ident=str(100000+i);posts.append({'id':ident,'key':'benchmark:'+ident,'owner':'benchmark','author':'fixture','text':text,'sources':['bookmarks'],'url':'https://example.com/'+ident,'links':[],'media':[]})
        w.import_backup(data={'format':'gold-collector','version':1,'posts':posts})
        expected={p['text']:p['observation_id'] for p in w.records()}
        if args.mode!='keyword':w.index_attachments()
        w.close();cold=[];warm=[]
        for offset in range(3):
            receiver,sender=multiprocessing.Pipe(False);process=multiprocessing.Process(target=serve,args=(folder,sender));process.start();sender.close()
            try:
                if not receiver.poll(20):raise RuntimeError('Benchmark server did not start')
                port=receiver.recv();query,text=CASES[offset];cold.append(sample(port,query,expected[text],args.mode))
                for _ in range(2):
                    for query,text in CASES:warm.append(sample(port,query,expected[text],args.mode))
            finally:receiver.close();process.terminate();process.join(10)
        result={'scope':'Synthetic labelled corpus; HTTP search plus first 20-row page. Cold = fresh server process (OS disk cache not flushed). Warm = existing server process. UI paint is excluded.', 'mode':args.mode,'posts':args.posts,'cold':summary(cold),'warm':summary(warm),'budgets':{'cold_p95_ms':args.cold_budget_ms,'warm_p95_ms':args.warm_budget_ms,'expected_source_hit_at_5':1.0},'measurements':{'cold':cold,'warm':warm}}
        result['passed']=result['cold']['p95_ms']<=args.cold_budget_ms and result['warm']['p95_ms']<=args.warm_budget_ms and all(s['hit_at_5'] and not s['fallback'] for s in cold+warm)
        report=json.dumps(result,indent=2)
        if args.output:pathlib.Path(args.output).write_text(report+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='measurements'},indent=2))
        if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
