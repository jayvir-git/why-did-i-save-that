"""Plan or resume all attachment jobs, with at most four local worker processes."""
import pathlib,sys,json,concurrent.futures,argparse
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from gold_workspace import Workspace
from gold_workspace.enrichment import plan
def run(job_id):
    w=Workspace();j=w.job(job_id)
    while j['state'] not in ['completed','partial','failed','cancelled']:
        j=w.run_job(job_id,max_items=1)
        if j['progress']['cursor']%25==0:print(json.dumps({'job':job_id,'done':j['progress']['cursor'],'total':len(j['payload']['items']),'errors':len(j['progress']['errors'])}),flush=True)
    w.close();return {'job':job_id,'state':j['state'],'done':j['progress']['cursor'],'errors':len(j['progress']['errors'])}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true');args=parser.parse_args()
    w=Workspace();path=w.path/'attachment-plan.json'
    previous=json.loads(path.read_text()) if path.exists() else None
    p=previous if previous and previous.get('snapshot')==w.revision() else plan(w)
    path.write_text(json.dumps(p,indent=2),encoding='utf-8');w.close();print(json.dumps(p),flush=True)
    if args.run:
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
            for r in pool.map(run,p['jobs']):print(json.dumps(r),flush=True)
