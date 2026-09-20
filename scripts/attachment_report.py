"""Live local progress plus automatic, reproducible grouping after extraction settles."""
import pathlib,sys,json,time,html,collections,re,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from gold_workspace import Workspace
from gold_workspace.enrichment import enriched_records
def write_atomic(path,text):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(text,encoding='utf-8');tmp.replace(path)
def publish(w):
    s=w.enrichment_status();done=sum(j['done'] for j in s['jobs']);errors=sum(j['errors'] for j in s['jobs']);finished=all(j['state'] in ['completed','partial','failed','cancelled'] for j in s['jobs'])
    types=collections.Counter();textful=0
    for r in w.db.execute('SELECT o.raw,o.text FROM asset_cache c JOIN observations o ON o.id=c.observation_id'):
        raw=json.loads(r[0]);mime=raw['mime'];types['images' if mime.startswith('image/') else 'PDFs' if mime=='application/pdf' else 'pages']+=1
        if mime.startswith('image/') and r[1].strip():textful+=1
    s.update(processed=done,failed=errors,types=dict(types),images_with_ocr_text=textful,finished=finished,updated=time.time())
    write_atomic(w.path/'attachment-progress.json',json.dumps(s,indent=2))
    e=html.escape
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="30"><title>Attachment enrichment</title><style>body{max-width:950px;margin:40px auto;padding:0 24px;font:17px/1.65 system-ui;background:#f5f3ed;color:#242923}h1{font-size:34px}progress{width:100%;height:22px;accent-color:#345a43}section{border-bottom:1px solid #ccc;padding:16px 0}small{color:#596354}a{color:#285443}code{overflow-wrap:anywhere}summary{cursor:pointer}</style><h1>Reading the attachments</h1>'''
    page+=f'<p><strong>{done:,} / {s["unique_urls"]:,}</strong> URLs processed · <strong>{s["extracted_urls"]:,}</strong> extracted · <strong>{errors:,}</strong> failed.</p><progress value="{done}" max="{s["unique_urls"]}"></progress><p>{"Extraction pass finished. Some URLs failed; this is not full visual/video understanding." if finished else "Running locally in four workers. Progress is checkpointed after every attachment."}</p><section><h2>Evidence recovered</h2><p>{types["pages"]:,} pages · {types["PDFs"]:,} PDFs · {types["images"]:,} images processed; {textful:,} images contain recognized text.</p><p>OCR text, source bytes and agent visual interpretations are separate. Images still need visual interpretation; thumbnails do not count as analyzed videos. Shortened links are resolved where publicly accessible. Failed access is recorded without bypassing it.</p></section>'
    page+='<section><h2>Agent access</h2><p><code>python -m gold_workspace attachment_query</code> produces a stable result set of posts plus extracted evidence. <code>visual_queue</code> returns local image paths and parent-post references; <code>annotate_asset</code> stores an interpretation with uncertainty.</p><p>When this pass finishes, this worker will export the enriched corpus and produce new groups from its text. Those automatic groups will remain provisional.</p><a href="enriched-groups.html">Open enriched groups when ready</a></section><section><h2>Batch progress</h2>'
    for j in s['jobs']:
        full=w.job(j['id']);role=full['payload']['items'][0].get('role','asset')
        page+=f'<p>{e(role)}: {j["done"]}/{j["total"]} · {e(j["state"])} · {j["errors"]} failed</p>'
    page+='</section><p><small>This page refreshes every 30 seconds while the report worker runs. Keep the computer awake for processing; jobs can resume after interruption. No original saves are deleted.</small></p></html>'
    write_atomic(w.path/'attachment-progress.html',page);return finished
def regroup(w):
    sys.path.insert(0,str(ROOT/'.runtime'));import numpy as np
    p=json.loads((w.path/'attachment-plan.json').read_text());rows=list(enriched_records(w,p['snapshot']))
    stop=set('the and that this with for you your are have was from they not but just like what can how more will all about its into when who their has been our out one would https com www twitter x it to of a in is on i be as at by we an or do so if my me github read use using get also'.split())
    words=[]
    for row in rows:
        text='\n'.join([row['text'],row.get('context',''),*[a.get('text','') for a in row['attachments']]])
        words.append(collections.Counter(t for t in re.findall(r'[^\W\d_]{3,}',text.lower()) if t not in stop))
    df=collections.Counter(t for c in words for t in c);vocab=[t for t,n in df.most_common() if 3<=n<len(rows)*.5][:6000];index={t:i for i,t in enumerate(vocab)}
    x=np.zeros((len(rows),len(vocab)),dtype=np.float32)
    for i,c in enumerate(words):
        for t,n in c.items():
            if t in index:x[i,index[t]]=(1+np.log(n))*np.log((len(rows)+1)/(df[t]+1))
    norm=np.linalg.norm(x,axis=1);valid=np.flatnonzero(norm>0);x/=np.maximum(norm[:,None],1e-9)
    rng=np.random.default_rng(42);centers=x[rng.choice(valid,min(24,len(valid)),replace=False)].copy()
    for _ in range(30):
        labels=(x@centers.T).argmax(axis=1);new=np.array([x[labels==k].mean(axis=0) if np.any(labels==k) else centers[k] for k in range(len(centers))]);new/=np.maximum(np.linalg.norm(new,axis=1,keepdims=True),1e-9)
        if np.allclose(centers,new,atol=1e-5):break
        centers=new
    groups=[]
    for k,c in enumerate(centers):
        ids=[i for i in valid if labels[i]==k];ids.sort(key=lambda i:float(-(x[i]@c)))
        terms=[vocab[i] for i in np.argsort(-c)[:8]]
        groups.append({'cluster':k,'terms':terms,'count':len(ids),'members':[rows[i]['observation_id'] for i in ids],'examples':[{'url':rows[i]['url'],'text':rows[i]['text'][:300],'attachments':[{k:a[k] for k in ['url','role','coverage']} for a in rows[i]['attachments']]} for i in ids[:8]]})
    status=w.enrichment_status();complete=all(j['state'] in ['completed','partial','failed','cancelled'] for j in status['jobs'])
    result={'source_snapshot':p['snapshot'],'enrichment_revision':w.revision(),'extraction_settled':complete,'extracted_urls':status['extracted_urls'],'planned_urls':status['unique_urls'],'method':'TF-IDF over full post/context and all extracted attachment text; vocabulary 6000, spherical k-means k=24, seed42. Terms are provisional automatic group labels, not inferred motives. No manual categories or quality ranking applied.','posts':len(rows),'unassigned':int((norm==0).sum()),'groups':groups}
    write_atomic(w.path/'enriched-corpus.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in rows))
    write_atomic(w.path/'enriched-groups.json',json.dumps(result,ensure_ascii=False,indent=2))
    inv=w.investigate('Explore the collection using extracted links and image text',p['snapshot']);w.artifact(inv['id'],'enriched-groups','automatic-clusters',result)
    write_atomic(w.path/'enrichment-investigation.json',json.dumps(inv))
    e=html.escape;body='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Enriched groups</title><style>body{max-width:1000px;margin:40px auto;padding:20px;background:#f5f3ed;color:#242923;font:16px/1.6 system-ui}details{border-bottom:1px solid #ccc;padding:15px 0}summary{cursor:pointer;font-weight:600}a{color:#285443}li{margin:14px 0}</style><h1>Groups after reading attachments</h1><p>'+e(result['method'])+'</p><p>Media understanding remains incomplete: OCR cannot explain an image, and thumbnails do not replace video content. Failures remain in the progress report. These groups use a different representation from the first MiniLM pass, so changes cannot be attributed solely to enrichment.</p>'
    body+=f'<p><strong>{"Extraction pass settled" if complete else "Partial checkpoint: extraction is still running"}</strong> · {status["extracted_urls"]} of {status["unique_urls"]} URLs extracted. Failed URLs remain missing evidence.</p>'
    for g in groups:
        body+=f'<details><summary>{e(" / ".join(g["terms"][:5]))} — {g["count"]} posts</summary><ul>'
        for ex in g['examples']:
            body+='<li><a href="'+e(ex['url'],quote=True)+'">'+e(ex['text'] or '[No primary text]')+'</a><br><small>'+e('; '.join(a['coverage'] for a in ex['attachments']))+'</small></li>'
        body+='</ul></details>'
    body+='<p><a href="attachment-progress.html">Extraction coverage</a></p></html>';write_atomic(w.path/'enriched-groups.html',body)
if __name__=='__main__':
    w=Workspace()
    while not publish(w):time.sleep(20)
    regroup(w);publish(w);w.close()
