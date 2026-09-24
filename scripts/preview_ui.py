"""Disposable UI preview: synthetic saves, no access to your real collection.

Run `python scripts/preview_ui.py`, then open http://127.0.0.1:8770.
Ctrl+C stops the preview and removes its temporary workspace.
"""
import argparse
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from gold_workspace import Workspace
from gold_workspace.app import server


def seed(path):
    posts = []
    examples = [
        ('linastudio', 'A small website is a good place to start. Choose one useful idea, write the content first, and give it room to breathe. A collection of practical tools for building a website.'),
        ('samreads', 'Learning something new? Try recalling it before rereading it. These study techniques turn a saved article into something you can actually use.'),
        ('fieldnotes', 'Creative project ideas for a quiet weekend: a neighborhood walking guide, a personal reading log, or a website for a friend. Start small. Finish something.'),
    ]
    for index in range(24):
        author, text = examples[index % len(examples)]
        if index == 0:
            text += ' Targetpicker fixture with two attachments.'
        if index == 3:
            text += '\n\n' + 'Good website design makes the next step obvious. ' * 22
        post_id = str(123456 + index)
        posts.append({'key': f'preview:{post_id}', 'id': post_id, 'owner': 'preview', 'author': author, 'text': text,
                      'sources': ['bookmarks'], 'url': f'https://example.com/posts/{post_id}', 'links': [], 'media': [],
                      'postedAt': '2026-09-01T12:00:00Z', 'status': 'inbox', 'note': '', 'reasons': []})
    workspace = Workspace(path)
    try:
        posts[0]['links'] = ['https://example.com/attachment-a','https://example.com/attachment-b']
        workspace.import_backup(data={'format': 'gold-collector', 'version': 1, 'posts': posts})
        parent = next(p for p in workspace.records() if p['id'] == '123456')['observation_id']
        for suffix in ['a','b']:
            url='https://example.com/attachment-'+suffix
            value=workspace._resource({'raw':('Attachment '+suffix).encode(),'text':'Captured attachment '+suffix,'url':url,'source_url':url,'mime':'text/plain','coverage':'text','extractor':'preview-fixture'})
            with workspace.db:
                workspace.db.execute('INSERT INTO asset_refs VALUES(?,?,?)',(parent,url,'link'))
                workspace.db.execute('INSERT INTO asset_cache VALUES(?,?)',(url,value['observation_id']))
    finally:
        workspace.close()


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8770);args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='gold-ui-preview-') as path:
        seed(path)
        app = server(path, port=args.port)
        print(f'Disposable UI preview: http://127.0.0.1:{args.port}', flush=True)
        try:
            app.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            app.server_close()
