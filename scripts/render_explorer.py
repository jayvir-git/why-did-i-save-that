"""Render a private, searchable attachment explorer from a pinned discovery run."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gold_workspace import Workspace


def main():
    w = Workspace(); folder = w.path
    grouped = json.loads((folder / 'refined-groups.json').read_text(encoding='utf-8'))
    rows = [json.loads(line) for line in (folder / 'refined-corpus.jsonl').read_text(encoding='utf-8').split('\n') if line]
    label_path = folder / 'reviewed-group-labels.json'
    labels = json.loads(label_path.read_text(encoding='utf-8')) if label_path.exists() else {}
    if labels and labels.get('enrichment_revision') != grouped['enrichment_revision']:
        raise ValueError('Group labels belong to another enrichment revision; review before reusing them')
    assets = {}; posts = []
    for row in rows:
        refs = []
        for a in row['attachments']:
            key = a.get('observation_id') or a['url']
            if key not in assets:
                asset = dict(a)
                if a.get('observation_id'):
                    raw = json.loads(w.db.execute('SELECT raw FROM observations WHERE id=?', (key,)).fetchone()[0])
                    if raw.get('mime','').startswith('image/'):
                        asset['image'] = 'blobs/' + raw['raw_blob']
                    asset['uncertainties'] = raw.get('uncertainties', [])
                assets[key] = asset
            if key not in refs: refs.append(key)
        oid = row['observation_id']; assignment = grouped['assignments'].get(oid)
        posts.append({'id': oid, 'url': row['url'], 'text': row['text'], 'quote': (row.get('quotedPost') or {}).get('text', ''), 'author': row.get('author', ''), 'assets': refs, 'assignment': assignment})
    for group in grouped['groups']:
        label = labels.get('groups', {}).get(str(group['id']), {})
        group.update(label)
        group.setdefault('label', ' / '.join(group['terms'][:4]))
        group.setdefault('assessment', 'Unreviewed automatic group')
    reviewed = json.loads((folder / 'visual-review-sample.json').read_text(encoding='utf-8'))
    data = {'grouping': grouped, 'posts': posts, 'assets': assets, 'visual_reviews': reviewed, 'extraction': w.enrichment_status()}
    (folder / 'reviewed-discovery.json').write_text(json.dumps(grouped, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder / 'evidence-explorer-data.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    page = (ROOT / 'scripts/evidence_explorer.html').read_text(encoding='utf-8')
    baseline = folder / 'enriched-groups-baseline.html'
    if not baseline.exists(): baseline.write_bytes((folder / 'enriched-groups.html').read_bytes())
    for filename in ['evidence-explorer.html', 'enriched-groups.html']:
        (folder / filename).write_text(page, encoding='utf-8')
    inv = w.investigate('Refine attachment discovery with balanced semantic grouping and inspected visual evidence', grouped['source_snapshot'])
    w.artifact(inv['id'], 'refined-discovery', 'reviewed-exploration', {'grouping': grouped, 'visual_reviews': reviewed, 'coverage': 'All posts computationally grouped; group review covers saved representatives only; eight images inspected in this pass. Videos not watched.'})
    (folder / 'refined-investigation.json').write_text(json.dumps(inv), encoding='utf-8')
    print(json.dumps({'posts': len(posts), 'groups': len(grouped['groups']), 'visual_reviews': len(reviewed), 'investigation': inv['id']}))
    w.close()


if __name__ == '__main__': main()
