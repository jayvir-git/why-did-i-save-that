"""Run a repeatable local research sweep; judgments are saved separately after review."""
import json
import pathlib
import sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from gold_workspace import Workspace

QUERIES=[
    'Archive Twitter bookmarks and liked posts to portable Markdown files',
    'Personal knowledge base semantic search retrieve rerank evidence citations',
    'Research agents persistent memory resumable investigation source provenance',
    'Extract web articles images video transcripts into searchable knowledge',
    'Evaluate information retrieval quality search relevance benchmarks',
]

if __name__=='__main__':
    w=Workspace();index=w.index_attachments()
    investigation=w.investigate('What in my saves could help improve this very tool?',index['source_snapshot'])
    searches=[]
    for query in QUERIES:
        r=w.attachment_semantic(query,index_id=index['index_id'],threshold=.3)
        rows=w.result(r['receipt']['result_id'],limit=10)['rows']
        searches.append({'query':query,'receipt':r['receipt'],'top_results':rows})
        print(json.dumps({'query':query,'matches':r['receipt']['count'],'top':[{'post_id':x['observation_id'],'score':round(x['score'],3),'post':x['text'][:130],'source':x['supporting_passages'][0]['url'],'evidence_id':x['supporting_passages'][0]['observation_id'],'excerpt':x['supporting_passages'][0]['embedding_text'][:440]} for x in rows[:6]]},ensure_ascii=True),flush=True)
    result={'investigation':investigation,'index':index,'searches':searches}
    w.artifact(investigation['id'],'search-sweep','retrieval-evidence',result)
    (w.path/'tool-investigation-searches.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    w.close()
