"""Render an authored, evidence-linked investigation without fetching remote content."""
import html
import json
import pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
FOLDER=ROOT/'workspace-data'


def main():
    d=json.loads((FOLDER/'tool-research.json').read_text(encoding='utf-8'));e=html.escape
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>What your saves can teach this tool</title><style>body{max-width:1000px;margin:38px auto;padding:0 24px;background:#f5f3ed;color:#242923;font:16px/1.65 system-ui}h1{font-size:30px;line-height:1.2;max-width:780px}h2{font-size:22px}h3{font-size:18px}a{color:#285443}small{color:#60685d}section{padding:22px 0;border-top:1px solid #cbd0c3}summary{cursor:pointer;color:#285443}blockquote{border-left:3px solid #b6c3ad;margin:18px 0;padding:6px 18px;white-space:pre-wrap}img{max-width:100%;max-height:600px;object-fit:contain}code{overflow-wrap:anywhere;font-size:13px}.stats{display:flex;gap:30px;flex-wrap:wrap;margin:25px 0}.stats strong{font-size:24px;display:block}.status{font-size:12px;text-transform:uppercase;letter-spacing:.06em}li{margin:8px 0}.note{border-left:3px solid #285443;padding:8px 18px;background:#e9ecdf}</style><p><a href="enriched-groups.html">Back to the evidence explorer</a></p>'''
    page+='<h1>'+e(d['question'])+'</h1><p>'+e(d['conclusion'])+'</p>'
    page+='<div class="stats"><div><strong>7</strong>saved design findings</div><div><strong>5</strong>images inspected</div><div><strong>3</strong>rejected candidate examples</div></div>'
    page+='<p class="note">These are patterns found in your captured sources, not endorsements of advertised products. The archive was researched locally; no external tools were installed or accounts connected.</p>'
    page+='<section><h2>What now works</h2><ul>'+''.join('<li>'+e(x)+'</li>' for x in d['implementation_this_pass'])+'</ul><p>Agents can search by meaning and retrieve supporting passages without opening Chrome. The index stores up to three excerpts per source; it does not cover every passage in a long document.</p></section>'
    md=['# '+d['question'],'',d['conclusion'],'',d['review_scope'],'']
    for n,f in enumerate(d['findings'],1):
        page+='<section><div class="status">'+e(f['decision'])+'</div><h2>'+str(n)+'. '+e(f['title'])+'</h2><p>'+e(f['source_summary'])+'</p><h3>Application to this tool</h3><p>'+e(f['application'])+'</p><p><small>'+e(f['limits'])+'</small></p>'
        page+='<details><summary>Inspect the supporting evidence</summary><p><a href="'+e(f['post_url'],quote=True)+'">Saved post</a> · <a href="'+e(f['source_url'],quote=True)+'">Attachment source</a></p><blockquote>'+e(f['evidence']['quote'])+'</blockquote>'
        if f['image']:page+='<img loading="lazy" src="'+e(f['image'],quote=True)+'" alt="Captured source image supporting this finding">'
        if f.get('visual_interpretation'):page+='<p><strong>Agent visual interpretation:</strong> '+e(f['visual_interpretation']['text'])+'</p>'
        if f['id'] in ['portable-archive','comparison-set']:
            page+='<p>Also inspected: '+ ' · '.join('<a href="'+e(x['url'],quote=True)+'">'+e(x['name'])+'</a>' for x in d.get('supplementary_sources',[]))+'</p>'
        page+='<p><small>Exact source span '+str(f['evidence']['start'])+'–'+str(f['evidence']['end'])+' · <code>'+e(f['evidence']['observation_id'])+'</code>. Text-span validation checks fidelity; the design application is an agent judgment.</small></p></details></section>'
        md.extend(['## '+f['title'],'',f['source_summary'],'','Application: '+f['application'],'','Limits: '+f['limits'],'','[Saved post]('+f['post_url']+') · [Source]('+f['source_url']+')','',f"Evidence: {f['evidence']['observation_id']} [{f['evidence']['start']}:{f['evidence']['end']}]",'','> '+f['evidence']['quote'].replace('\n','\n> '),''])
    page+='<section><h2>Rejected candidates are part of the result</h2><p>These surfaced in semantic retrieval and were rejected after inspection. A high similarity score is not a relevance verdict.</p><ul>'
    for r in d['rejected']:page+='<li>'+e(r['reason'])+' <a href="'+e(r['url'],quote=True)+'">Source post</a></li>'
    page+='</ul></section><section><h2>Checks and coverage</h2><p>'+e(d['review_scope'])+'</p><ul>'
    checks=d['verification']['checks']
    for c in checks:page+='<li>'+e(c['query'])+' — expected source at rank <strong>'+str(c['rank'])+'</strong>.</li>'
    page+='</ul><p>'+str(sum(c['top_10_spans_verified'] for c in checks))+' supporting spans checked against their immutable source text. These three convenience queries are smoke tests, not an independent quality benchmark.</p><details><summary>Searches used in the investigation</summary><ul>'
    for s in d['searches']:page+='<li>'+e(s['query'])+' — '+str(s['receipt']['count'])+' threshold matches. Only selected results were reviewed.</li>'
    page+='</ul></details><h3>Still unfinished</h3><ul>'+''.join('<li>'+e(x)+'</li>' for x in d['not_implemented'])+'</ul></section>'
    page+='<section><h2>Continue from the saved work</h2><p><a href="tool-research.md">Readable research bundle</a> · <a href="tool-research.json">Full findings and evidence</a> · <a href="research-index.json">Compact research manifest</a></p><details><summary>Agent interface</summary><p><code>Workspace.attachment_semantic(text, index_id=None, threshold=0.3)</code> returns a stable result handle. Use <code>result</code> to read supporting passages and <code>get</code> for the complete source. The same operations are exposed by the CLI and MCP catalog.</p><p>Investigation: <code>'+e(d['investigation_id'])+'</code></p></details></section></html>'
    (FOLDER/'tool-research.html').write_text(page,encoding='utf-8')
    md.extend(['## Rejected candidates','',*[r['reason']+' [Source]('+r['url']+')' for r in d['rejected']],'','## Continue','','Investigation: '+d['investigation_id'],'','Full records: tool-research.json; compact entry point: research-index.json.'])
    (FOLDER/'tool-research.md').write_text('\n'.join(md),encoding='utf-8')
    print('Rendered tool-research.html and tool-research.md')

if __name__=='__main__':main()
