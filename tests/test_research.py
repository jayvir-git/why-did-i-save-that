import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch
from gold_workspace import Workspace
from gold_workspace.app import server
from gold_workspace.attachment_search import passages
from test_workspace import backup
from test_attachment_search import fake_embed


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.w=Workspace(self.tmp.name)
        self.w.import_backup(data=backup('Evidence for retrieval systems.'))
    def tearDown(self):
        self.w.close(); self.tmp.cleanup()
    def test_browse_is_complete_stable_and_does_not_use_semantics(self):
        data = backup()
        for ident, date in [('123457','2025-01-01T00:00:00Z'),('123458',None)]:
            post = dict(data['posts'][0], id=ident, key='tester:'+ident, postedAt=date)
            data['posts'].append(post)
        self.w.import_backup(data=data)
        with patch.object(self.w, 'attachment_semantic', side_effect=AssertionError('Browse must not embed')):
            result = self.w.search_library('')
        rid = result['receipt']['result_id']
        rows = self.w.result(rid)['rows']
        self.assertEqual(len(rows), 3)
        self.assertEqual([r['postedAt'] for r in rows], ['2025-01-01T00:00:00Z','2024-01-01T00:00:00Z',None])
        for row in rows:
            for span in row['supporting_passages']:
                self.assertEqual(self.w.get([span['observation_id']])[0]['text'][span['start']:span['end']], span['quote'])
        self.w.import_backup(data=backup('A changed post'))
        self.assertEqual(self.w.result(rid, offset=1, limit=1)['rows'], rows[1:2])
    def test_full_document_coverage_and_exact_bounded_spans(self):
        text=' '.join('word'+str(i) for i in range(1000))+' &amp; conclusion'
        chunks=passages(text,set())
        joined=' '.join(c['embedding_text'] for c in chunks)
        for i in range(1000): self.assertIn('word'+str(i),joined)
        for c in chunks:
            self.assertEqual(c['quote'],text[c['start']:c['end']])
            self.assertLess(len(c['quote']),1200)
    def test_research_versions_and_stale_evidence(self):
        oid=self.w.records()[0]['observation_id']; inv=self.w.investigate('Search design')['id']
        self.w.claim(inv,'finding','Uses evidence',[{'observation_id':oid,'start':0,'end':8,'quote':'Evidence'}])
        self.assertFalse(self.w.research_search('evidence')['rows'][0]['changed_evidence'])
        self.w.import_backup(data=backup('Updated captured source.'))
        result=self.w.research_search('evidence')['rows'][0]
        self.assertEqual(result['changed_evidence'],[oid])
        self.w.artifact(inv,'other','note',{'text':'Alternative design'})
        self.w.connect_research(inv,'finding',inv,'other','contradicts','Different design assumptions')
        self.assertEqual(self.w.research_search('')['receipt']['count'],3)
    def test_media_import_is_searchable_and_immutable(self):
        oid=self.w.records()[0]['observation_id']
        req=self.w.request_media(oid,'Transcribe this clip')
        self.assertEqual(self.w.request_media(oid,'Transcribe this clip')['id'],req['id'])
        self.w.complete_media(req['id'],'00:01 --> 00:04\nUnique transcript phrase',kind='transcript')
        result=self.w.search_library('unique transcript',mode='keyword')
        self.assertEqual(result['receipt']['count'],1)
        self.assertEqual(self.w.get([oid])[0]['text'],'Evidence for retrieval systems.')
        with self.assertRaises(ValueError):self.w.complete_media(req['id'],'overwrite')
    def test_hybrid_and_explicit_fallback(self):
        with patch('gold_workspace.attachment_search.embed',side_effect=fake_embed):
            self.w.index_attachments()
            result=self.w.search_library('retrieval')
            row=self.w.result(result['receipt']['result_id'])['rows'][0]
            self.assertEqual(set(row['ranks']),{'keyword','semantic'})
        with patch.object(self.w,'attachment_semantic',side_effect=RuntimeError('Model unavailable')):
            self.assertEqual(self.w.search_library('retrieval')['receipt']['fallback'],'Model unavailable')
    def test_workspace_backup_restores_research_without_pairing_token(self):
        import zipfile
        from scripts.backup_workspace import backup as archive_workspace
        inv=self.w.investigate('Backup fixture')['id']
        self.w.artifact(inv,'note','note',{'text':'Retained research'})
        (self.w.path/'bridge-token.txt').write_text('fixture-secret')
        archive=archive_workspace(self.w.path)
        with tempfile.TemporaryDirectory() as restored:
            with zipfile.ZipFile(archive) as z:
                self.assertNotIn('bridge-token.txt',z.namelist())
                z.extractall(restored)
            other=Workspace(restored)
            self.assertEqual(other.inventory()['posts'],1)
            self.assertEqual(other.read_artifact(inv,'note')['content']['text'],'Retained research')
            other.close()

    def test_web_rejects_other_origins_and_private_paths(self):
        app=server(self.tmp.name,0);thread=threading.Thread(target=app.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{app.server_port}'
        try:
            for path in ['/workspace.sqlite','/bridge-token.txt','/../workspace-data/bridge-token.txt']:
                with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(base+path)
                self.assertEqual(e.exception.code,404);e.exception.close()
            data=json.dumps({'operation':'inventory'}).encode()
            bad=urllib.request.Request(base+'/api',data,headers={'Content-Type':'application/json','Origin':'https://example.com'})
            with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(bad)
            self.assertEqual(e.exception.code,403);e.exception.close()
            good=urllib.request.Request(base+'/api',data,headers={'Content-Type':'application/json','Origin':base})
            with urllib.request.urlopen(good) as r:self.assertEqual(json.load(r)['posts'],1)
            unsafe=urllib.request.Request(base+'/api',json.dumps({'operation':'sql','args':{'statement':'SELECT 1'}}).encode(),headers={'Content-Type':'application/json','Origin':base})
            with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(unsafe)
            e.exception.close()
        finally:app.shutdown();app.server_close();thread.join()

if __name__=='__main__':unittest.main()

class SearchReuseTests(unittest.TestCase):
    setUp = ResearchTests.setUp
    tearDown = ResearchTests.tearDown
    def test_queries_reuse_corpus_across_connections_and_refresh_after_import(self):
        from gold_workspace.enrichment import enriched_records
        with patch('gold_workspace.enrichment.enriched_records', wraps=enriched_records) as reads:
            self.w.search_library('retrieval', mode='keyword')
            other = Workspace(self.tmp.name)
            try:
                other.search_library('systems', mode='keyword')
            finally:
                other.close()
            self.assertEqual(reads.call_count, 1, 'Search must not rebuild the entire corpus for each HTTP connection')
            self.w.import_backup(data=backup('Fresh vocabulary'))
            self.assertEqual(self.w.search_library('vocabulary', mode='keyword')['receipt']['count'], 1)
            self.assertEqual(self.w.search_library('retrieval', mode='keyword')['receipt']['count'], 0)
            self.assertEqual(reads.call_count, 2)

    def test_completion_invalidates_warm_search(self):
        self.assertEqual(self.w.search_library('transcript',mode='keyword')['receipt']['count'],0)
        oid=self.w.records()[0]['observation_id']
        req=self.w.request_media(oid,'Explain')
        self.w.complete_media(req['id'],'Unique transcript phrase')
        self.assertEqual(self.w.search_library('transcript',mode='keyword')['receipt']['count'],1)

    def test_unreadable_model_falls_back_to_keyword(self):
        with patch.object(self.w,'attachment_semantic',side_effect=PermissionError('Model files are not readable')):
            result=self.w.search_library('retrieval')
            self.assertEqual(result['receipt']['count'],1)
            self.assertIn('not readable',result['receipt']['fallback'])
