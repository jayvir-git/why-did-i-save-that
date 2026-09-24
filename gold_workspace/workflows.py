"""User-facing actions with durable receipts, evidence targets and observable work."""
import hashlib
import json
import time
import uuid

SCHEMA = '''
CREATE TABLE IF NOT EXISTS action_receipts(id TEXT PRIMARY KEY, payload TEXT NOT NULL, result TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS work_runs(id TEXT PRIMARY KEY, kind TEXT NOT NULL, target TEXT NOT NULL, state TEXT NOT NULL, message TEXT NOT NULL, result TEXT, created REAL NOT NULL, updated REAL NOT NULL, heartbeat REAL NOT NULL, last_event REAL NOT NULL);
CREATE TABLE IF NOT EXISTS work_run_providers(run_id TEXT PRIMARY KEY REFERENCES work_runs(id),provider TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_run ON work_runs(kind,target) WHERE state IN ('queued','starting','running');
CREATE TABLE IF NOT EXISTS source_actions(id TEXT PRIMARY KEY,observation_id TEXT NOT NULL REFERENCES observations(id),reason TEXT NOT NULL,next_action TEXT NOT NULL,due_date TEXT NOT NULL,state TEXT NOT NULL,outcome TEXT NOT NULL,version INTEGER NOT NULL,updated REAL NOT NULL);
'''


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


class WorkflowMixin:
    def _receipt(self, client_request_id, payload, write):
        if not isinstance(client_request_id,str) or not 8 <= len(client_request_id) <= 160:
            raise ValueError('A stable client request ID is required')
        payload = encoded(payload)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            previous = self.db.execute('SELECT * FROM action_receipts WHERE id=?',(client_request_id,)).fetchone()
            if previous:
                if previous['payload'] != payload: raise ValueError('Request ID already used for different content; reconcile that action first')
                return json.loads(previous['result'])
            result = write()
            self.db.execute('INSERT INTO action_receipts VALUES(?,?,?,?)',(client_request_id,payload,encoded(result),time.time()))
            return result

    def action_outcome(self, client_request_id):
        row = self.db.execute('SELECT result FROM action_receipts WHERE id=?',(client_request_id,)).fetchone()
        return {'state':'committed','result':json.loads(row[0])} if row else {'state':'not_found'}

    def save_note(self, client_request_id, title, text, evidence=None):
        title=title.strip(); text=text.strip(); evidence=evidence or []
        if not title or len(title)>240 or not text: raise ValueError('A title (up to 240 characters) and note are required')
        self.validate_evidence(evidence)
        def write():
            ident='investigation_'+uuid.uuid4().hex
            self.db.execute('INSERT INTO investigations VALUES(?,?,?,?)',(ident,title,self.revision(),time.time()))
            content={'statement':text,'evidence':evidence,'counterevidence':[],'assumptions':[], 'status':'proposed','validation':'Exact spans verified; support for the conclusion is not automatically verified'} if evidence else {'text':text,'status':'unverified'}
            kind='claim' if evidence else 'note'
            self.db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,?,?)',(ident,title,1,kind,'user',encoded(content),time.time()))
            return {'investigation_id':ident,'name':title,'version':1,'kind':kind}
        return self._receipt(client_request_id,{'operation':'save_note','title':title,'text':text,'evidence':evidence},write)

    def queue_review(self, client_request_id, observation_id, objective):
        self.get([observation_id]); objective=objective.strip()
        if not objective: raise ValueError('A review question is required')
        self._media_table()
        def write():
            old=self.db.execute("SELECT id,version FROM media_requests WHERE observation_id=? AND objective=? AND state='pending'",(observation_id,objective)).fetchone()
            if old:return {'id':old['id'],'state':'pending','version':old['version']}
            ident='media_'+uuid.uuid4().hex
            self.db.execute('INSERT INTO media_requests VALUES(?,?,?,?,?,?,?)',(ident,observation_id,objective,'pending',1,None,time.time()))
            return {'id':ident,'state':'pending','version':1}
        return self._receipt(client_request_id,{'operation':'queue_review','observation_id':observation_id,'objective':objective},write)

    def save_review(self, client_request_id, request_id, description, kind='visual', expected_version=1, uncertainties=None):
        self._media_table(); description=description.strip()
        if not description or kind not in ('visual','transcript'):raise ValueError('Review text and a valid review type are required')
        payload={'operation':'save_review','request_id':request_id,'description':description,'kind':kind,'expected_version':expected_version,'uncertainties':uncertainties or []}
        # Immutable files can be created before the transaction; all database changes
        # (resource, annotation, request state, receipt) commit or roll back together.
        raw_hash=self.blob(description)
        resource={'text':description,'raw_blob':raw_hash,'extractor':'imported-'+kind+'-v1','coverage':'imported_'+kind,'mime':'text/plain','uncertainties':uncertainties or []}
        def write():
            row=self.db.execute('SELECT * FROM media_requests WHERE id=?',(request_id,)).fetchone()
            if not row or row['state']!='pending' or row['version']!=expected_version:raise ValueError('Review state changed; refresh before saving')
            source=self.get([row['observation_id']])[0]
            value={**resource,'url':source['raw'].get('url',''),'source_observation':source['id'],'captured_at':time.time(),'object_key':kind+':'+request_id}
            raw=encoded(value); digest=hashlib.sha256(raw.encode()).hexdigest(); oid='obs_'+digest
            revision=self.db.execute('INSERT INTO revisions(created,source,hash) VALUES(?,?,?)',(time.time(),'review',digest)).lastrowid
            self.db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?,?,?,?)',(oid,'resource:'+hashlib.sha256(value['object_key'].encode()).hexdigest(),revision,raw,description,'','',None,'resource'))
            result={'observation_id':oid,'revision':revision,'request_id':request_id,'version':expected_version+1}
            self.db.execute("UPDATE media_requests SET state='completed',version=version+1,result=? WHERE id=?",(encoded(result),request_id))
            self.db.execute('INSERT OR IGNORE INTO asset_annotations VALUES(?,?)',(row['observation_id'],oid))
            return result
        return self._receipt(client_request_id,payload,write)

    def source_targets(self, observation_id):
        """Enumerate actual attachments, including uncaptured ones; never choose for UI."""
        from .enrichment import canonical
        source=self.get([observation_id])[0]; raw=source['raw']
        def target(record, role, url=None):
            r=record['raw']; mime=r.get('mime',''); blob=r.get('raw_blob','')
            return {'observation_id':record['id'],'role':role,'url':url or r.get('url',''),'text':record['text'][:1200],
                'coverage':r.get('coverage','captured_post' if record['kind']=='post' else 'extracted_text'),
                'image_available':mime in ('image/png','image/jpeg','image/webp','image/gif') and (self.path/'blobs'/blob).is_file(),
                'text_available':bool(record['text'].strip()),'can_review':True}
        targets=[target(source,'post' if source['kind']=='post' else raw.get('role','attachment'))]
        refs=[(r['url'],r['role']) for r in self.db.execute('SELECT url,role FROM asset_refs WHERE source_observation=?',(observation_id,))]
        refs += [(u,'link') for u in raw.get('links',[])]
        refs += [(m.get('url',''),'image' if m.get('type')=='photo' else 'video_thumbnail') for m in raw.get('media',[])]
        seen=set()
        for url,role in refs:
            url=canonical(url)
            if not url or (url,role) in seen:continue
            seen.add((url,role)); cached=self.db.execute('SELECT observation_id FROM asset_cache WHERE url=?',(url,)).fetchone()
            if cached:targets.append(target(self.get([cached[0]])[0],role,url))
            else:targets.append({'observation_id':None,'role':role,'url':url,'text':'','coverage':'not_extracted','image_available':False,'text_available':False,'can_review':False})
        for r in self.db.execute('SELECT annotation_observation FROM asset_annotations WHERE asset_observation=?',(observation_id,)):
            targets.append(target(self.get([r[0]])[0],'interpretation'))
        return {'source_observation':observation_id,'targets':targets}

    def workspace_status(self):
        self._media_table()
        runs=self.work_status()['runs']
        source_signature=encoded([self.revision(),[tuple(r) for r in self.db.execute('SELECT * FROM asset_cache ORDER BY url')],self.db.execute('SELECT count(*) FROM asset_annotations').fetchone()[0]])
        notes=tuple(self.db.execute('SELECT count(*),max(created) FROM artifacts').fetchone())
        reviews=[tuple(r) for r in self.db.execute('SELECT id,state,version FROM media_requests ORDER BY id')]
        actions=tuple(self.db.execute('SELECT count(*),max(updated) FROM source_actions').fetchone())
        index=None; index_error=None
        try:
            pointer=json.loads((self.path/'attachment-search-latest.json').read_text(encoding='utf-8'))
            # Small receipt sidecar avoids reading a large index just to poll freshness.
            path=self.path/'attachment-indexes'/(pointer['index_id']+'.receipt.json')
            index=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'index_id':pointer['index_id'],'enrichment_revision':None}
        except FileNotFoundError:pass
        except (ValueError,KeyError,OSError):index_error='Meaning index status is unreadable; rebuild it.'
        return {'revision':self.revision(),'sources_token':hashlib.sha256(source_signature.encode()).hexdigest(),
            'notes_token':encoded(notes),'reviews_token':encoded(reviews),'actions_token':encoded(actions),'runs':runs,
            'index':index,'index_error':index_error,'index_stale':bool(index and index.get('enrichment_revision') is not None and index['enrichment_revision']<self.revision())}

    def save_source_action(self, client_request_id, observation_id, reason='', next_action='', due_date='', state='planned', outcome='', expected_version=0):
        import datetime
        self.get([observation_id])
        if state not in ('planned','done'):raise ValueError('Action state must be planned or done')
        if not next_action.strip():raise ValueError('Describe the next action')
        if state=='done' and not outcome.strip():raise ValueError('Record what happened before marking done')
        if due_date:datetime.date.fromisoformat(due_date)
        payload=dict(operation='save_source_action',observation_id=observation_id,reason=reason,next_action=next_action,due_date=due_date,state=state,outcome=outcome,expected_version=expected_version)
        def write():
            ident='action_'+observation_id
            old=self.db.execute('SELECT version FROM source_actions WHERE id=?',(ident,)).fetchone()
            version=old[0] if old else 0
            if version!=expected_version:raise ValueError('Action changed; refresh before saving')
            self.db.execute('INSERT OR REPLACE INTO source_actions VALUES(?,?,?,?,?,?,?,?,?)',(ident,observation_id,reason.strip(),next_action.strip(),due_date,state,outcome.strip(),version+1,time.time()))
            return {'id':ident,'version':version+1,'state':state}
        return self._receipt(client_request_id,payload,write)

    def source_action(self, observation_id):
        self.get([observation_id])
        row=self.db.execute('SELECT * FROM source_actions WHERE observation_id=?',(observation_id,)).fetchone()
        return dict(row) if row else {'observation_id':observation_id,'version':0}

    def source_actions(self):
        rows=[dict(r) for r in self.db.execute("SELECT a.*,o.text AS source_text FROM source_actions a JOIN observations o ON o.id=a.observation_id ORDER BY state DESC,due_date='' ASC,due_date ASC,updated DESC")]
        return self._result(rows,{'method':'User-authored source actions and outcomes'})

    def start_work(self, client_request_id, kind, target, provider='codex'):
        from .runner import launch
        if kind not in ('review','index','extract'):raise ValueError('Unknown work type')
        if provider not in ('codex','claude'):raise ValueError('Choose codex or claude as the review provider')
        if kind!='review' and provider!='codex':raise ValueError('Provider selection applies only to reviews')
        if kind=='review':
            self._media_table(); row=self.db.execute('SELECT * FROM media_requests WHERE id=?',(target,)).fetchone()
            if not row or row['state']!='pending':raise ValueError('Choose a pending review')
        elif kind=='index':target='library'
        else:
            # target is a JSON descriptor, restricted to an actual reference on a saved source.
            descriptor=json.loads(target); options=self.source_targets(descriptor['observation_id'])['targets']
            if not any(t['url']==descriptor.get('url') and t['role']==descriptor.get('role') for t in options):raise ValueError('Choose an attachment from this source')
            target=encoded(descriptor)
        def write():
            active=self.db.execute("SELECT id FROM work_runs WHERE kind=? AND target=? AND state IN ('queued','starting','running')",(kind,target)).fetchone()
            if active:return {'id':active[0]}
            if self.db.execute("SELECT count(*) FROM work_runs WHERE state IN ('queued','starting','running')").fetchone()[0]>=2:
                raise ValueError('Two tasks are already running. Wait for one to finish or cancel it in Activity.')
            ident='run_'+uuid.uuid4().hex; now=time.time()
            self.db.execute('INSERT INTO work_runs VALUES(?,?,?,?,?,?,?,?,?,?)',(ident,kind,target,'queued','Queued for local worker',None,now,now,now,now))
            self.db.execute('INSERT INTO work_run_providers VALUES(?,?)',(ident,provider))
            return {'id':ident}
        payload={'operation':'start_work','kind':kind,'target':target}
        if provider!='codex':payload['provider']=provider
        receipt=self._receipt(client_request_id,payload,write)
        launch(self.path,receipt['id'])
        return self.work_status(receipt['id'])['runs'][0]

    def work_status(self, run_id=None):
        # A stale heartbeat is an interrupted worker, not an invented provider failure.
        with self.db:
            self.db.execute("UPDATE work_runs SET state='interrupted',message='Worker stopped responding. Retry to start a new attempt.',updated=? WHERE state IN ('queued','starting','running') AND heartbeat<?",(time.time(),time.time()-45))
        rows=self.db.execute('SELECT * FROM work_runs WHERE id=?' if run_id else 'SELECT * FROM work_runs ORDER BY created DESC LIMIT 50',(run_id,) if run_id else ()).fetchall()
        return {'runs':[{**dict(r),'provider':self.work_provider(r['id']),'result':json.loads(r['result']) if r['result'] else None} for r in rows]}

    def work_provider(self, run_id):
        row=self.db.execute('SELECT provider FROM work_run_providers WHERE run_id=?',(run_id,)).fetchone()
        return row[0] if row else 'codex'

    def cancel_work(self, run_id):
        with self.db:self.db.execute("UPDATE work_runs SET state='cancelled',message='Cancelled. Any completed extraction remains saved.',updated=? WHERE id=? AND state IN ('queued','starting','running')",(time.time(),run_id))
        return self.work_status(run_id)
