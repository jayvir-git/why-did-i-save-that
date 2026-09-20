"""Disposable UI preview: synthetic saves, no access to your real collection.

Run `python scripts/preview_ui.py`, then open http://127.0.0.1:8770.
Ctrl+C stops the preview and removes its temporary workspace.
"""
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
        if index == 3:
            text += '\n\n' + 'Good website design makes the next step obvious. ' * 22
        post_id = str(123456 + index)
        posts.append({'key': f'preview:{post_id}', 'id': post_id, 'owner': 'preview', 'author': author, 'text': text,
                      'sources': ['bookmarks'], 'url': f'https://example.com/posts/{post_id}', 'links': [], 'media': [],
                      'postedAt': '2026-09-01T12:00:00Z', 'status': 'inbox', 'note': '', 'reasons': []})
    workspace = Workspace(path)
    try:
        workspace.import_backup(data={'format': 'gold-collector', 'version': 1, 'posts': posts})
    finally:
        workspace.close()


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='gold-ui-preview-') as path:
        seed(path)
        app = server(path, port=8770)
        print('Disposable UI preview: http://127.0.0.1:8770', flush=True)
        try:
            app.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            app.server_close()
