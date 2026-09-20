"""Rebuild the evidence explorer without fetching anything or changing source captures."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gold_workspace import Workspace
from gold_workspace.discovery import cluster
from gold_workspace.enrichment import enriched_records


def main():
    w = Workspace()
    snapshot = json.loads((w.path / 'attachment-plan.json').read_text())['snapshot']
    rows = list(enriched_records(w, snapshot))
    result = cluster(rows, semantic_cache=w.path / 'discovery-embedding-cache.json')
    result.update(source_snapshot=snapshot, enrichment_revision=w.revision(), posts=len(rows))
    (w.path / 'refined-groups.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    by_id = {r['observation_id']: r for r in rows}
    review = []
    for g in result['groups']:
        review.append({**{k: g[k] for k in ['id', 'terms', 'count']}, 'examples': [
            {'id': oid, 'url': by_id[oid]['url'], 'text': by_id[oid]['text'][:600], 'evidence': [
                {'id': a.get('observation_id'), 'role': a['role'], 'text': a.get('text', '')[:850]}
                for a in by_id[oid]['attachments'] if a.get('text')][:3]}
            for oid in g['review_sample']]})
    (w.path / 'refined-review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding='utf-8')
    (w.path / 'refined-corpus.jsonl').write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows), encoding='utf-8')
    print(json.dumps({'posts': len(rows), 'groups': len(result['groups']), 'unassigned': len(result['unassigned']), 'boilerplate_lines': result['boilerplate_lines']}))
    w.close()


if __name__ == '__main__': main()
