"""Derived discovery signals. Never rewrite captured evidence or infer save intent."""
import collections
import html
import re
import urllib.parse

STOP = set('''a about above after again against all almost alone along already also although always am among an and another any anyone anything are around as at back be became because become been before behind being below between both but by can cannot could did do does doing done down during each either else enough even ever every everyone everything few first for former from further get gets getting give given go goes going got had has have having he her here hers herself him himself his how however i if in indeed into is it its itself just keep last latter least less like made make many may me might mine more most mostly much must my myself neither never new next no nobody none nor not nothing now of off often on once one only onto or other others otherwise our ours ourselves out over own part perhaps please put quite rather really same say says see seem several she should since so some someone something sometimes still such take than that the their theirs them themselves then there these they thing things think third this those though through throughout thus to together too toward two under until up upon us use used using very via want was we well were what whatever when where whether which while who whoever whom whose why will with within without would yes yet you your yours yourself yourselves
http https www com amp quot nbsp twitter quoted post posts imgflip views subscribers subscribed subscribe subscription share retweet likes reply replies ago hours hour minutes minute days day months month years year home playlists community latest popular oldest read more click follow following followers sign login copyright rights reserved cookie cookies privacy policy terms conditions navigation menu powered readme fork forks stars star branches branch tags license permalink loading permalink add file files edited view video videos welcome today yesterday tomorrow everyone someone anyone something anything everything don doesn didn isn aren wasn weren won ve ll re im dont thats its lets ive thats really actually literally bro lol lmao nice good great best better bad know people man guys guy way time lot come comes let looks look need needs still also just hai hain mein aur toh hai nahi
'''.split())
UI_LINE = re.compile(r'^(?:[\d.,KM]+\s*(?:views?|likes?|subscribers?|followers?)\b|(?:accept|reject) all cookies|sign (?:in|up)\b|all rights reserved)', re.I)


def tokens(value):
    value = html.unescape(value or '').lower()
    value = re.sub(r'https?://\S+|@[\w_]+', ' ', value)
    return [t for t in re.findall(r'[^\W\d_]{3,}', value) if t not in STOP]


def asset_identity(a):
    u = urllib.parse.urlsplit(a['url'])
    if u.hostname == 'pbs.twimg.com':
        return u.hostname + re.sub(r'\.(?:png|jpg|jpeg|webp)$', '', u.path)
    return a.get('observation_id') or a['url']


def repeated_lines(rows):
    documents = {}
    for row in rows:
        for a in row['attachments']:
            if a.get('text') and a['role'] != 'visual_interpretation':
                documents.setdefault(asset_identity(a), a['text'])
    counts = collections.Counter()
    for text in documents.values():
        counts.update(set(line.strip().casefold() for line in text.splitlines() if 12 <= len(line.strip()) <= 180))
    return {line for line, count in counts.items() if count >= 12}


def source_parts(row, boilerplate):
    primary = collections.Counter(tokens(row.get('text', '') + '\n' + (row.get('quotedPost') or {}).get('text', '')))
    unique = {}
    for a in row['attachments']:
        body = a.get('text', '')
        cleaned = '\n'.join(line for line in body.splitlines() if line.strip().casefold() not in boilerplate and not UI_LINE.search(line.strip()))
        c = collections.Counter(tokens(cleaned))
        if not c:
            continue
        # Alternative sizes and short-link aliases must not multiply evidence weight.
        key = ('interpretation', a.get('observation_id')) if a['role'] == 'visual_interpretation' else asset_identity(a)
        if key not in unique or sum(c.values()) > sum(unique[key].values()):
            unique[key] = c
    seen = set(); attachments = []
    for c in unique.values():
        signature = tuple(sorted(c.items()))
        if signature not in seen:
            attachments.append(c); seen.add(signature)
    return primary, attachments


def semantic_vectors(rows, boilerplate, cache_path):
    import hashlib
    import json
    from .semantic import embed
    from .enrichment import runtime
    runtime()
    import numpy as np
    cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    texts = {}; plans = []
    def keys(body):
        body = html.unescape(body)
        body = '\n'.join(line for line in body.splitlines() if line.strip().casefold() not in boilerplate and not UI_LINE.search(line.strip()))
        body = re.sub(r'https?://\S+|@[\w_]+', ' ', body)
        words = body.split()
        if not tokens(body): return []
        # Bounded retrieval representation; complete evidence remains in corpus export.
        starts = [0] if len(words) <= 140 else sorted(set([0, max(0, len(words)//2 - 60), max(0, len(words)-120)]))
        result = []
        for start in starts:
            text = ' '.join(words[start:start+120]); key = hashlib.sha256(('minilm-evidence-v1:' + text).encode()).hexdigest()
            texts[key] = text; result.append(key)
        return result
    for row in rows:
        p = keys(row.get('text', '') + '\n' + (row.get('quotedPost') or {}).get('text', ''))
        assets = {}
        for a in row['attachments']:
            key = ('annotation', a.get('observation_id')) if a['role'] == 'visual_interpretation' else asset_identity(a)
            if len(a.get('text','')) > len(assets.get(key, '')): assets[key] = a['text']
        aa = [keys(body) for body in dict.fromkeys(assets.values())]; aa = [a for a in aa if a]
        plans.append((p, aa))
    missing = [key for key in texts if key not in cache]
    print(f'Embedding {len(missing)} new excerpts; {len(texts)-len(missing)} cached', flush=True)
    for offset in range(0, len(missing), 24):
        batch = missing[offset:offset+24]
        cache.update(zip(batch, embed([texts[key] for key in batch])))
        if offset % 240 == 0 or offset+24 >= len(missing):
            tmp = cache_path.with_suffix('.tmp'); tmp.write_text(json.dumps(cache), encoding='utf-8'); tmp.replace(cache_path)
            print(f'Embedded {min(offset+24,len(missing))}/{len(missing)}', flush=True)
    def pooled(keys):
        v = np.mean([cache[key] for key in keys], axis=0).astype(np.float32)
        return v / max(float(np.linalg.norm(v)), 1e-9)
    x = np.zeros((len(rows),384), dtype=np.float32)
    for i, (p, aa) in enumerate(plans):
        pv = pooled(p) if p else np.zeros(384,dtype=np.float32)
        av = np.mean([pooled(a) for a in aa], axis=0) if aa else np.zeros(384,dtype=np.float32)
        av /= max(float(np.linalg.norm(av)),1e-9)
        weight = .15 if len(tokens(rows[i].get('text',''))) < 8 else .4
        x[i] = weight*pv+(1-weight)*av if pv.any() and av.any() else pv+av
    return x


def cluster(rows, k=32, semantic_cache=None):
    from .enrichment import runtime
    runtime()
    import numpy as np
    boilerplate = repeated_lines(rows)
    parts = [source_parts(r, boilerplate) for r in rows]
    df = collections.Counter(t for p, aa in parts for t in set(p).union(*(set(a) for a in aa)))
    vocab = [t for t, n in df.most_common() if 3 <= n < len(rows) * .45][:6000]
    index = {t: i for i, t in enumerate(vocab)}
    idf = np.array([np.log((len(rows) + 1) / (df[t] + 1)) for t in vocab], dtype=np.float32)
    def vector(c):
        v = np.zeros(len(vocab), dtype=np.float32)
        for t, n in c.items():
            if t in index: v[index[t]] = 1 + np.log(n)
        v *= idf
        return v / max(float(np.linalg.norm(v)), 1e-9)
    x = np.zeros((len(rows), len(vocab)), dtype=np.float32)
    for i, (p, aa) in enumerate(parts):
        pv = vector(p)
        av = np.mean([vector(a) for a in aa], axis=0) if aa else np.zeros(len(vocab), dtype=np.float32)
        av /= max(float(np.linalg.norm(av)), 1e-9)
        x[i] = .45 * pv + .55 * av if pv.any() and av.any() else pv + av
    lexical = x.copy()
    if semantic_cache is not None: x = semantic_vectors(rows, boilerplate, semantic_cache)
    norms = np.linalg.norm(x, axis=1); valid = np.flatnonzero(norms > 0)
    if not len(valid): return {'groups': [], 'assignments': {}, 'unassigned': [r['observation_id'] for r in rows], 'boilerplate_lines': len(boilerplate)}
    x /= np.maximum(norms[:, None], 1e-9); xv = x[valid]
    best = None
    for seed in [42, 43, 44]:
        rng = np.random.default_rng(seed); centers = xv[rng.choice(len(valid), min(k, len(valid)), replace=False)].copy()
        for _ in range(40):
            labels = (xv @ centers.T).argmax(axis=1)
            new = np.array([xv[labels == j].mean(axis=0) if (labels == j).any() else centers[j] for j in range(len(centers))])
            new /= np.maximum(np.linalg.norm(new, axis=1, keepdims=True), 1e-9)
            converged = np.allclose(centers, new, atol=1e-5); centers = new
            if converged: break
        scores = xv @ centers.T; labels = scores.argmax(axis=1); objective = float(scores.max(axis=1).sum())
        if best is None or objective > best[0]: best = objective, centers, scores, labels, seed
    _, centers, scores, labels, seed = best
    assignments = {}; groups = []
    for j, center in enumerate(centers):
        members = [i for i in range(len(valid)) if labels[i] == j]
        members.sort(key=lambda i: -float(scores[i, j]))
        ids = [rows[valid[i]]['observation_id'] for i in members]
        for i in members:
            ordered = np.argsort(-scores[i]); top = float(scores[i, j]); second = int(ordered[1]) if len(ordered) > 1 else j
            assignments[rows[valid[i]]['observation_id']] = {'group': j, 'similarity': round(top, 4), 'alternative': second, 'margin': round(top - float(scores[i, second]), 4)}
        term_vector = lexical[[valid[i] for i in members]].mean(axis=0) if members else np.zeros(len(vocab))
        groups.append({'id': j, 'terms': [vocab[i] for i in np.argsort(-term_vector)[:10]], 'members': ids, 'count': len(ids), 'review_sample': ids[:4] + ids[-1:]})
    method = 'Source-balanced local MiniLM, up to three 120-word excerpts per source (start/middle/end), 32 spherical k-means groups; primary text weight .4, or .15 for fewer than eight signal words; attachments receive the balance. This bounded representation does not encode every word of long documents.' if semantic_cache is not None else 'Source-balanced TF-IDF, 32 spherical k-means groups; primary text weight .45, attachments .55.'
    return {'groups': groups, 'assignments': assignments, 'unassigned': [rows[i]['observation_id'] for i in range(len(rows)) if norms[i] == 0], 'boilerplate_lines': len(boilerplate), 'seed': seed, 'vocabulary': len(vocab), 'method': method + ' Each source normalized before pooling; duplicate image sizes and exact duplicate texts pooled once. Best clustering objective of seeds 42/43/44. UI terms and repeated short lines excluded from derived signals only. Similarities and margins are not calibrated confidence. No save motives inferred.'}
