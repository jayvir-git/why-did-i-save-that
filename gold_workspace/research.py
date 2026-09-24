"""Research memory and user-requested media work; original evidence stays immutable."""
import collections
import json
import math
import re
import time
import uuid
import threading

# Shared across short-lived HTTP Workspace connections; never cache SQLite handles.
_search_cache = collections.OrderedDict()
_search_lock = threading.Lock()


def lexical_index(w):
    from .enrichment import enriched_records
    # Results/notes do not affect retrieval. Include relationships as well as revisions:
    # enrichment can attach an already-stored resource without creating a revision.
    stamp = (w.revision(), tuple(tuple(r) for r in w.db.execute(
        "SELECT source_observation,url,role FROM asset_refs ORDER BY source_observation,url,role")),
        tuple(tuple(r) for r in w.db.execute("SELECT url,observation_id FROM asset_cache ORDER BY url")),
        tuple(tuple(r) for r in w.db.execute("SELECT * FROM asset_annotations ORDER BY 1,2")))
    identity = (str(w.path), (w.path / "workspace.sqlite").stat().st_ino)
    with _search_lock:
        cached = _search_cache.get(identity)
        if cached and cached[0] == stamp:
            _search_cache.move_to_end(identity)
            return cached[1]
        documents = []; postings = collections.defaultdict(set)
        for p in enriched_records(w):
            sources = [{"observation_id":p["observation_id"], "field":"text", "text":p["text"], "role":"post"}]
            for field, body in [("context",p.get("context","")), ("quotedPost.text",(p.get("quotedPost") or {}).get("text",""))]:
                if body: sources.append({"observation_id":p["observation_id"], "field":field, "text":body, "role":field})
            sources.extend({**a,"field":"text"} for a in p["attachments"] if a.get("text") and a.get("observation_id"))
            unique = {}
            for source in sources: unique.setdefault(source["text"],source)
            sources = list(unique.values())
            counts = collections.Counter(terms("\n".join(s["text"] for s in sources)))
            for term in counts: postings[term].add(len(documents))
            documents.append((p,sources,counts,sum(counts.values())))
        value = (documents, postings, sum(d[3] for d in documents)/max(len(documents),1) or 1)
        _search_cache[identity] = (stamp,value)
        _search_cache.move_to_end(identity)
        while len(_search_cache)>2: _search_cache.popitem(last=False)
        return value


def terms(text):
    return re.findall(r'\w+', text.casefold())


class ResearchMixin:
    def search_library(self, text, mode='hybrid'):
        if not text.strip():
            rows = []
            for p, _sources, _counts, _length in lexical_index(self)[0]:
                spans = []
                if p.get('text'):
                    spans.append({'observation_id':p['observation_id'], 'field':'text', 'role':'post', 'start':0, 'end':min(len(p['text']),600), 'quote':p['text'][:600]})
                for a in p.get('attachments', []):
                    if a.get('text') and a.get('observation_id'):
                        spans.append({'observation_id':a['observation_id'], 'field':'text', 'role':a.get('role','attachment'), 'coverage':a.get('coverage',''), 'start':0, 'end':min(len(a['text']),1200), 'quote':a['text'][:1200]})
                rows.append({'observation_id':p['observation_id'], 'url':p.get('url',''), 'text':p.get('text',''), 'author':p.get('author',''), 'postedAt':p.get('postedAt'), 'supporting_passages':spans, 'browsing':True})
            rows.sort(key=lambda r:(r.get('postedAt') or '',r['observation_id']), reverse=True)
            return self._result(rows, {'query':'', 'mode':'browse', 'method':'All current posts, newest posted date first; undated posts last', 'revision':self.revision()})
        if mode not in ('keyword', 'hybrid', 'semantic'):
            raise ValueError('Unknown search mode')
        query = set(terms(text))
        documents, postings, avg = lexical_index(self) if mode != 'semantic' else ([], {}, 1)
        n = len(documents)
        df = {t: len(postings.get(t, ())) for t in query}
        matching = set().union(*(postings.get(t, ()) for t in query))
        lexical = []
        for i in sorted(matching):
            p, sources, counts, length = documents[i]
            score = sum(math.log(1+(n-df[t]+.5)/(df[t]+.5))*counts[t]*2.2/(counts[t]+1.2*(.25+.75*length/avg)) for t in query if counts[t])
            if not score: continue
            evidence = []
            for s in sources:
                match = next((m for m in re.finditer(r'\w+', s['text']) if m[0].casefold() in query), None)
                if match:
                    lo, hi = max(0, match.start()-120), min(len(s['text']), match.end()+300)
                    evidence.append({k: v for k, v in {**s, 'start': lo, 'end': hi, 'quote': s['text'][lo:hi]}.items() if k != 'text'})
            lexical.append({'observation_id':p['observation_id'], 'url':p['url'], 'text':p['text'], 'author':p.get('author',''), 'postedAt':p.get('postedAt'), 'score':score, 'supporting_passages':evidence[:3]})
        lexical.sort(key=lambda r: (-r['score'], r['observation_id']))
        semantic = []; warning = None; semantic_receipt = None
        if mode != 'keyword':
            try:
                result = self.attachment_semantic(text)
                semantic_receipt = result['receipt']
                semantic = self.result(result['receipt']['result_id'], limit=10000)['rows']
            except (RuntimeError, OSError, ValueError) as e:
                if mode == 'semantic': raise
                warning = str(e)
        combined = {}
        for label, rows in [('keyword', lexical), ('semantic', semantic)]:
            for rank, row in enumerate(rows, 1):
                target = combined.setdefault(row['observation_id'], {**row, 'score':0., 'ranks':{}, 'supporting_passages':[]})
                target['score'] += 1/(60+rank)
                target['ranks'][label] = rank
                target['supporting_passages'].extend(row['supporting_passages'])
        rows = sorted(combined.values(), key=lambda r:(-r['score'],r['observation_id']))
        return self._result(rows, {'query':text, 'mode':mode, 'method':'Reciprocal rank fusion (k=60) of BM25 over captured text and local passage cosine; no learned reranker', 'revision':self.revision(), 'semantic_index':semantic_receipt, 'fallback':warning})

    def research_search(self, text=''):
        rows = []
        query = set(terms(text))
        for r in self.db.execute('SELECT a.*,i.objective,i.snapshot FROM artifacts a JOIN investigations i ON i.id=a.investigation_id WHERE a.version=(SELECT max(b.version) FROM artifacts b WHERE b.investigation_id=a.investigation_id AND b.name=a.name)'):
            content = json.loads(r['content'])
            hay = terms(r['name']+' '+r['objective']+' '+r['content'])
            score = sum(hay.count(t)/(len(hay)+1) for t in query)
            score += 10*sum(t in terms(r['name']) for t in query)
            if text and text.casefold()==r['name'].casefold(): score += 100
            if query and not score: continue
            changed = []
            if isinstance(content, dict):
                for e in content.get('evidence', []) + content.get('counterevidence', []):
                    if not isinstance(e, dict) or not e.get('observation_id'): continue
                    source = self.db.execute('SELECT object_id,revision FROM observations WHERE id=?',(e['observation_id'],)).fetchone()
                    if source and self.db.execute('SELECT max(revision) FROM observations WHERE object_id=?',(source['object_id'],)).fetchone()[0] > source['revision']:
                        changed.append(e['observation_id'])
            rows.append({**dict(r), 'content':content, 'score':score, 'changed_evidence':changed, 'newer_corpus_available':self.revision()>r['snapshot'], 'evidence_type':'derived_research_not_original_source'})
        rows.sort(key=lambda r:(-r['score'],-r['created'],r['name']))
        return self._result(rows, {'method':'Latest research versions, keyword-ranked separately from original evidence', 'query':text, 'staleness':'Changed captured source versions are flagged; remote sources are not automatically rechecked.'})

    def connect_research(self, investigation_id, name, target_investigation, target_name, relation, explanation, expected_version=0):
        if relation not in ('supports','contradicts','related','supersedes'):
            raise ValueError('Invalid relation')
        a = self.read_artifact(investigation_id, name)
        b = self.read_artifact(target_investigation, target_name)
        edge = {'source':{'investigation_id':investigation_id,'name':name,'version':a['version']}, 'target':{'investigation_id':target_investigation,'name':target_name,'version':b['version']}, 'relation':relation, 'explanation':explanation}
        import hashlib
        key = 'connection-'+hashlib.sha256(json.dumps([name,target_investigation,target_name,relation]).encode()).hexdigest()[:24]
        return self.artifact(investigation_id,key,'connection',edge,expected_version)

    def _media_table(self):
        self.db.execute('CREATE TABLE IF NOT EXISTS media_requests(id TEXT PRIMARY KEY,observation_id TEXT NOT NULL REFERENCES observations(id),objective TEXT NOT NULL,state TEXT NOT NULL,version INTEGER NOT NULL,result TEXT,created REAL NOT NULL)')

    def request_media(self, observation_id, objective):
        self.get([observation_id])
        if not objective.strip(): raise ValueError('Review objective required')
        self._media_table()
        old=self.db.execute("SELECT id FROM media_requests WHERE observation_id=? AND objective=? AND state='pending'",(observation_id,objective)).fetchone()
        if old: return {'id':old[0], 'state':'pending', 'duplicate':True}
        key='media_'+uuid.uuid4().hex
        with self.db:self.db.execute('INSERT INTO media_requests VALUES(?,?,?,?,?,?,?)',(key,observation_id,objective,'pending',1,None,time.time()))
        return {'id':key,'state':'pending','version':1}

    def media_requests(self, state='all'):
        if state not in ('all','pending','completed','cancelled'): raise ValueError('Invalid state')
        self._media_table()
        latest={r['target']:{**dict(r),'provider':self.work_provider(r['id']),'result':json.loads(r['result']) if r['result'] else None} for r in self.db.execute("SELECT r.* FROM work_runs r JOIN (SELECT target,max(created) AS created FROM work_runs WHERE kind='review' GROUP BY target) x ON r.target=x.target AND r.created=x.created WHERE r.kind='review'")}
        return self._result([{**dict(r),'latest_run':latest.get(r['id'])} for r in self.db.execute("SELECT * FROM media_requests WHERE state=? OR ?='all' ORDER BY created DESC",(state,state))], {'method':'Persistent review requests with their latest tracked execution; completion requires accepted analysis or transcript import'})

    def complete_media(self, request_id, description, kind='visual', uncertainties=None, expected_version=1):
        if kind not in ('visual','transcript'): raise ValueError('kind must be visual or transcript')
        if not description.strip(): raise ValueError('Analysis or transcript required')
        self._media_table()
        row=self.db.execute('SELECT * FROM media_requests WHERE id=?',(request_id,)).fetchone()
        if not row or row['version']!=expected_version or row['state']!='pending': raise ValueError('Unknown request or version conflict')
        # Transcript text (including optional VTT/SRT timecodes) remains separate from captured source text.
        source=self.get([row['observation_id']])[0]
        result=self._resource({'url':source['raw'].get('url',''),'raw':description.encode(),'text':description,'object_key':kind+':'+request_id+':'+__import__('hashlib').sha256(description.encode()).hexdigest(),'source_observation':row['observation_id'],'extractor':'imported-'+kind+'-v1','coverage':'imported_'+kind,'mime':'text/plain','uncertainties':uncertainties or []})
        with self.db:
            changed=self.db.execute("UPDATE media_requests SET state='completed',version=version+1,result=? WHERE id=? AND state='pending' AND version=?",(json.dumps(result),request_id,expected_version)).rowcount
            if changed!=1: raise ValueError('Request was completed by another worker')
            self.db.execute('INSERT OR IGNORE INTO asset_annotations VALUES(?,?)',(row['observation_id'],result['observation_id']))
        return {**result,'request_id':request_id,'version':expected_version+1}
