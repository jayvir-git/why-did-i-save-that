"""Local attachment extraction. Source bytes, OCR, and interpretations remain distinct."""
import pathlib,sys,json,re,io,urllib.parse,threading
ROOT=pathlib.Path(__file__).resolve().parents[1]
_local=threading.local()
def runtime():
    p=str(ROOT/'.runtime')
    if p not in sys.path:sys.path.insert(0,p)
def canonical(url):
    u=urllib.parse.urlsplit(url)
    if u.scheme not in ('https','http') or not u.hostname:return None
    return urllib.parse.urlunsplit((u.scheme,u.netloc,u.path,urllib.parse.urlencode([(k,v) for k,v in urllib.parse.parse_qsl(u.query,keep_blank_values=True) if not k.startswith('utm_')]),''))
def plan(w,snapshot=None,shards=4):
    assets={};revision=w._snapshot(snapshot)
    for p in w.records(revision):
        refs=[(u,'link') for u in p.get('links',[])]
        refs += [(m['url'],'image' if m.get('type')=='photo' else 'video_thumbnail') for m in p.get('media',[])]
        for url,role in refs:
            url=canonical(url)
            if not url or urllib.parse.urlsplit(url).hostname in ('x.com','twitter.com','www.x.com','www.twitter.com'):continue
            assets.setdefault(url,role)
            with w.db:w.db.execute('INSERT OR IGNORE INTO asset_refs VALUES(?,?,?)',(p['observation_id'],url,role))
    jobs=[]
    for role in ['link','image','video_thumbnail']:
        items=[{'url':u,'role':r} for u,r in sorted(assets.items()) if r==role]
        for n in range(shards):
            batch=items[n::shards]
            if batch:jobs.append(w.create_job('asset',batch,f'attachments-v1:{revision}:{role}:{n}:{shards}')['id'])
    return {'snapshot':revision,'unique_assets':len(assets),'roles':{r:sum(x==r for x in assets.values()) for r in set(assets.values())},'jobs':jobs}
def ocr(raw):
    runtime()
    from PIL import Image
    import numpy as np
    Image.MAX_IMAGE_PIXELS=25_000_000
    im=Image.open(io.BytesIO(raw));im.load();im=im.convert('RGB');size=im.size
    im.thumbnail((1800,1800))
    if not hasattr(_local,'ocr'):
        from rapidocr import RapidOCR
        _local.ocr=RapidOCR(params={'EngineConfig.onnxruntime.intra_op_num_threads':2,'EngineConfig.onnxruntime.inter_op_num_threads':1})
    out=_local.ocr(np.asarray(im)[:,:,::-1])
    texts=list(out.txts) if out.txts is not None else []
    scores=[float(x) for x in out.scores] if out.scores is not None else []
    boxes=out.boxes.tolist() if out.boxes is not None else []
    return {'text':'\n'.join(texts),'lines':[{'text':t,'score':s,'box':b} for t,s,b in zip(texts,scores,boxes)],'original_size':size,'ocr_size':im.size,'extractor':'rapidocr-3.9.2-default-v1','visual_analysis':'not_performed','language_limit':'Default OCR model; non-Latin and stylized text may be missed or misread.'}
def process_asset(w,item,operation_key=None):
    runtime()
    from .fetching import fetch_bytes,TextParser
    from .engine import digest,dumps
    url=item['url'];role=item.get('role','link')
    cached=w.db.execute('SELECT observation_id FROM asset_cache WHERE url=?',(url,)).fetchone()
    if cached:return {'observation_id':cached[0],'cached':True}
    value=fetch_bytes(url,max_bytes=12_000_000,media=True);raw=value['raw'];h=w.blob(raw)
    folder=w.path/'extraction-cache';folder.mkdir(exist_ok=True)
    cache=folder/(digest(h+':attachment-v1')+'.json')
    if cache.exists():result=json.loads(cache.read_text(encoding='utf-8'))
    elif value['mime'].startswith('image/'):
        result=ocr(raw)
        result['coverage']='ocr_only_needs_visual_analysis'
    elif value['mime']=='application/pdf':
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(raw));pages=[p.extract_text() or '' for p in reader.pages[:300]]
        result={'text':'\n\n'.join(pages),'pages':[{'page':n+1,'text':t} for n,t in enumerate(pages)],'extractor':'pypdf-6.19.0-v1','coverage':'text_layer_only','page_count':len(reader.pages),'pages_examined':len(pages),'truncated':len(reader.pages)>300,'visual_analysis':'not_performed'}
    else:
        decoded=raw.decode('utf-8',errors='replace')
        if value['mime']=='text/html':
            import trafilatura
            extracted=trafilatura.extract(decoded,include_tables=True,include_comments=False);fallback=not extracted
            if not extracted:
                parser=TextParser();parser.feed(decoded);extracted='\n'.join(''.join(parser.parts).splitlines())
            result={'text':extracted,'extractor':'html-fallback-v1' if fallback else 'trafilatura-2.2.0-v1','coverage':'html_text_only','visual_analysis':'not_performed'}
        else:result={'text':decoded,'extractor':'utf8-v1','coverage':'text','visual_analysis':'not_applicable'}
    if not cache.exists():
        tmp=cache.with_name(cache.name+'.'+__import__('uuid').uuid4().hex+'.tmp');tmp.write_text(dumps(result),encoding='utf-8');tmp.replace(cache)
    result={**result,'role':role,'source_url':url,'object_key':'asset:'+url,'raw':raw,'url':value['url'],'mime':value['mime'],'content_sha256':h}
    if role=='video_thumbnail' or 'video_thumb' in url:result['coverage']='thumbnail_only_playable_media_missing'
    if len(result['text'].strip())<50:result['needs_review']=True
    stored=w._resource(result,operation_key)
    with w.db:w.db.execute('INSERT OR REPLACE INTO asset_cache VALUES(?,?)',(url,stored['observation_id']))
    return {**stored,'coverage':result['coverage']}
def enriched_records(w,snapshot=None):
    posts=w.records(snapshot)
    for p in posts:
        attached=[]
        rows=w.db.execute('SELECT r.url,r.role,c.observation_id FROM asset_refs r LEFT JOIN asset_cache c ON c.url=r.url WHERE source_observation=?',(p['observation_id'],)).fetchall()
        for r in rows:
            if r['observation_id']:
                value=w.get([r['observation_id']])[0]
                host=urllib.parse.urlsplit(value['raw'].get('url','')).hostname or ''
                coverage=value['raw']['coverage'];body=value['text']
                if host in ['x.com','twitter.com','www.x.com','www.twitter.com']:
                    coverage='needs_authenticated_post_context';body=''
                elif host in ['youtube.com','www.youtube.com','youtu.be','m.youtube.com']:
                    coverage='needs_video_transcript';body=''
                attached.append({'observation_id':value['id'],'url':r['url'],'role':r['role'],'text':body,'coverage':coverage})
                for annotation in w.db.execute('SELECT o.id,o.text,o.raw FROM asset_annotations a JOIN observations o ON o.id=a.annotation_observation WHERE a.asset_observation=? AND o.revision=(SELECT max(x.revision) FROM observations x WHERE x.object_id=o.object_id)',(value['id'],)):
                    attached.append({'observation_id':annotation['id'],'url':r['url'],'role':'visual_interpretation','text':annotation['text'],'coverage':json.loads(annotation['raw']).get('coverage','agent_interpretation_not_source_authored')})
            else:attached.append({'url':r['url'],'role':r['role'],'coverage':'not_extracted'})
        for annotation in w.db.execute('SELECT o.id,o.text,o.raw FROM asset_annotations a JOIN observations o ON o.id=a.annotation_observation WHERE a.asset_observation=?',(p['observation_id'],)):
            attached.append({'observation_id':annotation['id'],'url':p['url'],'role':'visual_interpretation','text':annotation['text'],'coverage':json.loads(annotation['raw']).get('coverage','imported_analysis')})
        yield {**p,'attachments':attached}
