"""Local passage retrieval with exact source spans and immutable index manifests."""
import hashlib
import html
import json
import math
import pathlib
import re
import sys
import uuid

from .discovery import UI_LINE, asset_identity, repeated_lines, tokens
from .enrichment import enriched_records
from .semantic import MODEL, embed


def write_json(path, value):
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)


def passages(text, boilerplate):
    """Cover all cleaned words in overlapping 120-word passages, retaining exact original word spans."""
    words = []; offset = 0
    for line in text.splitlines(keepends=True):
        clean = html.unescape(line)
        if clean.strip().casefold() not in boilerplate and not UI_LINE.search(clean.strip()):
            for match in re.finditer(r'\S+', line):
                clean_word = re.sub(r'https?://\S+|@[\w_]+', ' ', html.unescape(match[0]))
                words.extend((word, offset+match.start(), offset+match.end()) for word in clean_word.split())
        offset += len(line)
    if not words or not tokens(' '.join(w[0] for w in words)): return []
    starts = list(range(0, max(1, len(words)-30), 90))
    out = []
    for start in starts:
        chunk = words[start:start+120]; clean = ' '.join(w[0] for w in chunk)
        lo, hi = chunk[0][1], chunk[-1][2]
        out.append({'start': lo, 'end': hi, 'quote': text[lo:hi], 'embedding_text': clean,
                    'cache_key': hashlib.sha256(('minilm-evidence-v1:' + clean).encode()).hexdigest()})
    return out


def build(w, snapshot=None):
    revision = w._snapshot(snapshot); enrichment_revision = w.revision()
    rows = list(enriched_records(w, revision)); boilerplate = repeated_lines(rows)
    sources = {}; parents = {}
    for row in rows:
        oid = row['observation_id']; parents[oid] = {'observation_id': oid, 'url': row['url'], 'text': row['text'], 'author': row.get('author','')}
        candidates = [{'observation_id': oid, 'field': 'text', 'role': 'post', 'text': row['text'], 'url': row['url'], 'coverage': 'captured_post'}]
        if (row.get('quotedPost') or {}).get('text'):
            candidates.append({'observation_id': oid, 'field': 'quotedPost.text', 'role': 'quote', 'text': row['quotedPost']['text'], 'url': row['url'], 'coverage': 'captured_quoted_post'})
        assets = {}
        for a in row['attachments']:
            if not a.get('text') or not a.get('observation_id'): continue
            identity = a['observation_id'] if a['role']=='visual_interpretation' else asset_identity(a)
            if identity not in assets or len(a['text']) > len(assets[identity]['text']): assets[identity] = a
        candidates.extend({**a, 'field':'text'} for a in assets.values())
        for c in candidates:
            key = c['observation_id'] + ':' + c['field']
            sources.setdefault(key, {**c, 'parents':set()})['parents'].add(oid)
    chunks = []
    for source_key, source in sources.items():
        for p in passages(source['text'], boilerplate):
            pid = hashlib.sha256((source_key + ':' + str(p['start']) + ':' + str(p['end']) + ':' + p['cache_key']).encode()).hexdigest()
            chunks.append({**p, 'passage_id':pid, 'observation_id':source['observation_id'], 'field':source['field'], 'role':source['role'], 'url':source['url'], 'coverage':source['coverage'], 'parents':sorted(source['parents'])})
    cache_path = w.path / 'discovery-embedding-cache.json'
    cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    required = {p['cache_key']:p['embedding_text'] for p in chunks}; missing = [k for k in required if k not in cache]
    print(f'Attachment search: {len(chunks)} passages; {len(required)-len(missing)} cached vectors, {len(missing)} to encode', file=sys.stderr, flush=True)
    for offset in range(0,len(missing),24):
        keys = missing[offset:offset+24]; cache.update(zip(keys,embed([required[k] for k in keys])))
        if offset % 240 == 0 or offset+24 >= len(missing):
            write_json(cache_path,cache)
            print(f'Encoded {min(offset+24,len(missing))}/{len(missing)}',file=sys.stderr,flush=True)
    for key in required:
        if len(cache[key]) != 384 or not all(math.isfinite(n) for n in cache[key]): raise ValueError('Invalid cached vector')
    index_id = hashlib.sha256(json.dumps([MODEL,revision,enrichment_revision,[p['passage_id'] for p in chunks]],sort_keys=True).encode()).hexdigest()
    indexed_parents = {parent for p in chunks for parent in p['parents']}
    receipt = {'index_id':index_id,'model':MODEL,'source_snapshot':revision,'enrichment_revision':enrichment_revision,'posts':len(rows),'indexed_posts':len(indexed_parents),'posts_without_passages':len(rows)-len(indexed_parents),'passages':len(chunks),'unique_vectors':len(required),'new_vectors':len(missing),'coverage':'All cleaned extracted text in overlapping 120-word passages (30-word overlap). Uncaptured pages, pixels and audio remain outside coverage. Full extracted text remains available through attachment_query/get. Exact quotes use original word offsets; fields identify primary text versus captured quote text.'}
    folder = w.path/'attachment-indexes'; folder.mkdir(exist_ok=True)
    path = folder/(index_id+'.json')
    if not path.exists(): write_json(path,{'receipt':receipt,'parents':parents,'passages':chunks,'vectors':{k:cache[k] for k in required}})
    write_json(w.path/'attachment-search-latest.json',{'index_id':index_id})
    return receipt


def search(w, text, index_id=None, threshold=.3):
    if not text.strip(): raise ValueError('Query text required')
    if not -1 <= threshold <= 1: raise ValueError('Threshold must be between -1 and 1')
    if index_id is None:
        pointer = w.path/'attachment-search-latest.json'
        if not pointer.exists(): raise ValueError('Run index_attachments first')
        index_id = json.loads(pointer.read_text(encoding='utf-8'))['index_id']
    if not re.fullmatch(r'[a-f0-9]{64}',index_id): raise ValueError('Invalid index ID')
    index = json.loads((w.path/'attachment-indexes'/(index_id+'.json')).read_text(encoding='utf-8'))
    query = embed([text])[0]
    qnorm = math.sqrt(sum(x*x for x in query))
    if len(query)!=384 or not qnorm or not all(math.isfinite(x) for x in query): raise ValueError('Invalid query vector')
    scores = {}
    for key, vector in index['vectors'].items():
        norm = math.sqrt(sum(x*x for x in vector))
        scores[key] = sum(a*b for a,b in zip(query,vector))/(qnorm*norm) if norm else -1
    matched = {}
    for p in index['passages']:
        score = scores[p['cache_key']]
        if score < threshold: continue
        evidence = {k:v for k,v in p.items() if k not in ['parents','cache_key']}
        evidence['score'] = score
        for parent in p['parents']: matched.setdefault(parent,[]).append(evidence)
    results = []
    for parent, evidence in matched.items():
        evidence.sort(key=lambda e:(-e['score'],e['passage_id']))
        # Keep the top three distinct excerpt texts. Shared evidence never boosts scores.
        selected = []; seen = set()
        for e in evidence:
            if e['embedding_text'] in seen: continue
            seen.add(e['embedding_text']); selected.append(e)
            if len(selected)==3: break
        results.append({**index['parents'][parent], 'score':selected[0]['score'], 'supporting_passages':selected})
    results.sort(key=lambda r:(-r['score'],r['observation_id']))
    return w._result(results,{**index['receipt'],'query':text,'threshold':threshold,'method':'Exact cosine scan over every indexed evidence excerpt; parent ranking is maximum passage score. Top three distinct supporting passages per post.','workspace_revision_now':w.revision(),'semantic_recall':'Unknown. Pinned index may predate new captures or annotations; similarity is not a relevance guarantee.'})
