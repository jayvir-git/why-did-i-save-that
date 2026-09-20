import json, pathlib, time

class JobsMixin:
    def create_job(self,kind,items,idempotency_key=None):
        from .engine import uid,dumps,digest
        if kind not in ['fetch','embed','extract_text','asset']:raise ValueError('Supported jobs: fetch, embed, extract_text, asset')
        if not isinstance(items,list):raise ValueError('items must be an array')
        key='job_'+digest(idempotency_key) if idempotency_key else uid('job')
        payload=dumps({'items':items})
        with self.db:
            old=self.db.execute('SELECT kind,payload FROM jobs WHERE id=?',(key,)).fetchone()
            if old:
                if old['kind']!=kind or old['payload']!=payload:raise ValueError('Idempotency key reused for different inputs')
            else:self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(key,kind,'pending',payload,dumps({'cursor':0,'results':[],'errors':[]}),time.time(),time.time()))
        return self.job(key)
    def job(self,job_id):
        r=self.db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        if not r:raise ValueError('Unknown job')
        return {**dict(r),'payload':json.loads(r['payload']),'progress':json.loads(r['progress'])}
    def cancel_job(self,job_id):
        self.job(job_id)
        with self.db:self.db.execute("UPDATE jobs SET state='cancelled',updated=? WHERE id=?",(time.time(),job_id))
        return self.job(job_id)
    def run_job(self,job_id,max_items=4,resume=False):
        from .engine import uid,dumps
        if not 1<=max_items<=100:raise ValueError('max_items must be 1..100; call again to resume')
        lease=uid('lease')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE');j=self.job(job_id)
            if j['state']=='running' and j['progress'].get('lease_until',0)>time.time():raise ValueError('Job is leased by another worker')
            if j['state']=='cancelled' and not resume:return j
            if j['state'] in ['completed','partial','failed']:return j
            p=j['progress'];p.update(lease=lease,lease_until=time.time()+300)
            self.db.execute("UPDATE jobs SET state='running',progress=?,updated=? WHERE id=?",(dumps(p),time.time(),job_id))
        items=j['payload']['items']
        for _ in range(max_items):
            current=self.job(job_id)
            if current['state']=='cancelled':return current
            if p['cursor']>=len(items):break
            item=items[p['cursor']]
            operation_key=f"{job_id}:{p['cursor']}"
            try:
                saved=self.db.execute('SELECT result FROM job_outputs WHERE operation_key=?',(operation_key,)).fetchone()
                if saved:result=json.loads(saved['result'])
                elif j['kind']=='fetch':result=self._fetch_resource(item,operation_key)
                elif j['kind']=='asset':
                    from .enrichment import process_asset
                    result=process_asset(self,item,operation_key)
                elif j['kind']=='embed':
                    from .semantic import MODEL,embed,chunks,text
                    record=self.get([item])[0];parts=chunks(text(record['raw']));vectors=[]
                    for start in range(0,len(parts),8):vectors.extend(embed(parts[start:start+8]))
                    with self.db:self.db.execute('INSERT OR REPLACE INTO vectors VALUES(?,?,?)',(item,MODEL,dumps(vectors)))
                    result={'observation_id':item,'chunks':len(vectors),'model':MODEL}
                else:
                    # Explicit local transcript/OCR adapter output: never called source-authored text.
                    source=self.get([item['observation_id']])[0]
                    value=pathlib.Path(item['path']).read_text(encoding='utf-8')
                    result=self._resource({'url':source['raw'].get('url',''),'source_observation':source['id'],'extractor':item.get('extractor','agent-supplied-extraction'),'mime':'text/plain','text':value,'raw':value.encode()},operation_key)
                p['results'].append({'item':item,'result':result})
            except Exception as error:p['errors'].append({'item':item,'error':str(error),'retryable':j['kind'] in ['fetch','asset']})
            p['cursor']+=1;p['lease_until']=time.time()+300
            with self.db:self.db.execute('UPDATE jobs SET progress=?,updated=? WHERE id=?',(dumps(p),time.time(),job_id))
        p.pop('lease',None);p.pop('lease_until',None)
        state=('partial' if p['results'] else 'failed') if p['errors'] else 'completed'
        if p['cursor']<len(items):state='pending'
        with self.db:self.db.execute("UPDATE jobs SET state=CASE WHEN state='cancelled' THEN state ELSE ? END,progress=?,updated=? WHERE id=?",(state,dumps(p),time.time(),job_id))
        return self.job(job_id)
    def retry_job(self,job_id):
        j=self.job(job_id)
        return self.create_job(j['kind'],[e['item'] for e in j['progress']['errors']])
    def _fetch_resource(self,url,operation_key=None):
        from .fetching import fetch
        return self._resource(fetch(url),operation_key)
    def _resource(self,value,operation_key=None):
        from .engine import dumps,digest
        raw_hash=self.blob(value.pop('raw'));value={**value,'raw_blob':raw_hash,'captured_at':time.time()};raw=dumps(value);h=self.blob(raw)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            if operation_key:
                saved=self.db.execute('SELECT result FROM job_outputs WHERE operation_key=?',(operation_key,)).fetchone()
                if saved:return json.loads(saved['result'])
            revision=self.db.execute('INSERT INTO revisions(created,source,hash) VALUES(?,?,?)',(time.time(),'enrichment',h)).lastrowid
            oid='obs_'+digest(raw)
            self.db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?,?,?,?)',(oid,'resource:'+digest(value.get('object_key') or value.get('source_observation') or value['url']),revision,raw,value['text'],'','',None,'resource'))
            result={'observation_id':oid,'revision':revision,'raw_blob':raw_hash,'text_characters':len(value['text']),'extractor':value['extractor']}
            if operation_key:self.db.execute('INSERT INTO job_outputs VALUES(?,?)',(operation_key,dumps(result)))
        return result
