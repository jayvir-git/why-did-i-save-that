"""Local MiniLM inference; model assets are bundled, and no remote loading exists."""
import json, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
MODEL='Xenova/all-MiniLM-L6-v2@751bff37182d3f1213fa05d7196b954e230abad9:q8:mean'
_runtime=None
def text(post):
    return '\n'.join(x for x in [post.get('text'),post.get('context'),(post.get('quotedPost') or {}).get('text'),*[m.get('alt') for m in post.get('media',[])]] if x).strip()
def fingerprint(post):
    a,b=2166136261,5381
    for c in text(post):
        n=ord(c);n=n if n<=65535 else 0xD800+((n-0x10000)>>10)
        a=((a^n)*16777619)&0xffffffff;b=((b*33)^n)&0xffffffff
    return f'minilm-v1:{a:x}:{b:x}'
def chunks(value):
    words=value.split();return [' '.join(words[i:i+120]) for i in range(0,len(words),90)]
def embed(texts):
    global _runtime
    if _runtime is None:
        sys.path.insert(0,str(ROOT/'.runtime'))
        try:import numpy as np;import onnxruntime as ort;from tokenizers import Tokenizer
        except ImportError as e:raise RuntimeError('Install requirements-workspace.txt into .runtime to enable local semantic search') from e
        folder=ROOT/'extension/models/Xenova/all-MiniLM-L6-v2'
        tokenizer=Tokenizer.from_file(str(folder/'tokenizer.json'));tokenizer.enable_padding(pad_id=0,pad_token='[PAD]');tokenizer.enable_truncation(max_length=512)
        options=ort.SessionOptions();options.intra_op_num_threads=2
        session=ort.InferenceSession(str(folder/'onnx/model_quantized.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
        _runtime=np,tokenizer,session
    np,tokenizer,session=_runtime
    encoded=tokenizer.encode_batch(texts)
    feed={'input_ids':np.array([x.ids for x in encoded],dtype=np.int64),'attention_mask':np.array([x.attention_mask for x in encoded],dtype=np.int64),'token_type_ids':np.array([x.type_ids for x in encoded],dtype=np.int64)}
    output=session.run(None,{i.name:feed[i.name] for i in session.get_inputs()})[0]
    mask=feed['attention_mask'][...,None];vectors=(output*mask).sum(axis=1)/mask.sum(axis=1)
    vectors/=np.maximum(np.linalg.norm(vectors,axis=1,keepdims=True),1e-12)
    return vectors.tolist()

class SemanticMixin:
    def index_attachments(self,snapshot=None):
        from .attachment_search import build
        return build(self,snapshot)
    def attachment_semantic(self,text,index_id=None,threshold=.3):
        from .attachment_search import search
        return search(self,text,index_id,threshold)
    def import_index(self,path):
        from .engine import dumps
        data=json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
        if data.get('version')!='minilm-v1':raise ValueError('Unsupported index version')
        posts={p['key']:p for p in self.records()};accepted=0
        with self.db:
            for r in data['records']:
                p=posts.get(r['key'])
                if not p or fingerprint(p)!=r['fingerprint']:continue
                import math
                if any(len(v)!=384 or any(not isinstance(x,(float,int)) or not math.isfinite(x) for x in v) for v in r['vectors']):raise ValueError('Invalid vectors')
                self.db.execute('INSERT OR REPLACE INTO vectors VALUES(?,?,?)',(p['observation_id'],MODEL,dumps(r['vectors'])));accepted+=1
        return {'accepted':accepted,'model':MODEL,'unmatched':len(data['records'])-accepted}
    def semantic(self,text,snapshot=None,threshold=0.23,owner=None,source=None,kind='post'):
        from .engine import dumps
        if not text.strip():raise ValueError('Query text required')
        if not -1<=threshold<=1:raise ValueError('Cosine threshold must be between -1 and 1')
        revision=self._snapshot(snapshot);posts=self.records(revision,kind);query=embed([text])[0];rows=[];indexed=0
        vectors={r[0]:json.loads(r[1]) for r in self.db.execute('SELECT observation_id,vectors FROM vectors WHERE model=?',(MODEL,))}
        for p in posts:
            if owner and p['owner']!=owner or source and source not in p['sources']:continue
            values=vectors.get(p['observation_id'])
            if values is None:continue
            indexed+=1
            score=max((sum(a*b for a,b in zip(v,query)) for v in values),default=-1)
            if score>=threshold:rows.append({**p,'score':score})
        rows.sort(key=lambda x:(-x['score'],x['object_id']))
        return self._result(rows,{'snapshot':revision,'method':'exact cosine scan over indexed text chunks','model':MODEL,'query':text,'threshold':threshold,'universe':len(posts),'indexed_in_scope':indexed,'scope_posts':sum((not owner or p['owner']==owner) and (not source or source in p['sources']) for p in posts),'filters':{'owner':owner,'source':source},'semantic_recall':'unknown; thresholded similarity is not exhaustive relevance','ranking':'maximum chunk cosine, descending'})
