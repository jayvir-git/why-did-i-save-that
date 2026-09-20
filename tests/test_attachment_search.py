import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from gold_workspace import Workspace
from gold_workspace.attachment_search import passages
from gold_workspace.enrichment import plan
from test_workspace import backup


def fake_embed(texts):
    vectors=[]
    for text in texts:
        # Controlled semantic fixture: distinct concepts, independent of retrieval code.
        if 'diagram' in text.lower(): v=[0.,0.,1.]
        elif 'retrieval' in text.lower() or 'find knowledge' in text.lower(): v=[1.,0.,0.]
        else: v=[0.,1.,0.]
        vectors.append(v+[0.]*381)
    return vectors


class AttachmentSearchTests(unittest.TestCase):
    def test_quoted_post_passages_can_be_used_directly_as_claim_evidence(self):
        with tempfile.TemporaryDirectory() as folder, patch('gold_workspace.attachment_search.embed',side_effect=fake_embed):
            w=Workspace(folder); b=backup('Saved this')
            b['posts'][0]['quotedPost']={'id':'987654','author':'other','text':'Retrieval retains source evidence.'}
            w.import_backup(data=b);w.index_attachments()
            r=w.attachment_semantic('find knowledge',threshold=.8)
            row=w.result(r['receipt']['result_id'])['rows'][0];passage=row['supporting_passages'][0]
            self.assertEqual(passage['field'],'quotedPost.text')
            inv=w.investigate('Check quoted source')
            evidence={k:passage[k] for k in ['observation_id','field','start','end','quote']}
            self.assertEqual(w.claim(inv['id'],'quote','The quoted source discusses retrieval.',[evidence])['version'],1)
            w.close()

    def test_source_spans_survive_html_and_interface_cleaning(self):
        source='Sign in\nSearch &amp; retrieval\n@account https://example.com\nSupporting evidence.\n'
        p=passages(source,set())[0]
        self.assertEqual(source[p['start']:p['end']],p['quote'])
        self.assertEqual(p['embedding_text'],'Search & retrieval Supporting evidence.')
        self.assertNotIn('Sign in',p['quote'])
        self.assertIn('&amp;',p['quote'])

    def test_shared_attachment_returns_both_parents_and_pinned_evidence(self):
        with tempfile.TemporaryDirectory() as folder, patch('gold_workspace.attachment_search.embed',side_effect=fake_embed):
            w=Workspace(folder); b=backup('Saved this'); b['posts'][0]['links']=['https://example.com/guide']
            b['posts'].append({**b['posts'][0],'id':'654321','key':'tester:654321','url':'https://x.com/writer/status/654321'})
            w.import_backup(data=b);plan(w,shards=1)
            source=w._resource({'raw':b'retrieval evidence','text':'Retrieval links evidence to sources.','url':'https://example.com/guide','source_url':'https://example.com/guide','mime':'text/plain','coverage':'text','extractor':'fixture'})
            with w.db:w.db.execute('INSERT INTO asset_cache VALUES(?,?)',('https://example.com/guide',source['observation_id']))
            index=w.index_attachments();result=w.attachment_semantic('find knowledge',threshold=.8)
            self.assertEqual(result['receipt']['count'],2)
            rows=w.result(result['receipt']['result_id'])['rows']
            for row in rows:
                p=row['supporting_passages'][0];text=w.get([p['observation_id']])[0]['text']
                self.assertEqual(text[p['start']:p['end']],p['quote'])
                self.assertEqual(p['role'],'link')
            w.annotate_asset(source['observation_id'],'A diagram of the pipeline')
            self.assertEqual(w.attachment_semantic('diagram',index_id=index['index_id'],threshold=.8)['receipt']['count'],0)
            w.index_attachments()
            self.assertEqual(w.attachment_semantic('diagram',threshold=.8)['receipt']['count'],2)
            self.assertEqual(w.result(result['receipt']['result_id'])['rows'],rows)
            with self.assertRaises(ValueError):w.attachment_semantic('find knowledge',index_id='../escape')
            w.close()

if __name__=='__main__':unittest.main()
