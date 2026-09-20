import json,pathlib,subprocess,sys,tempfile,unittest
from unittest.mock import patch
from gold_workspace import Workspace
from gold_workspace.fetching import validate_url

ROOT=pathlib.Path(__file__).resolve().parents[1]
def backup(text='A tutorial about building useful software.',sources=None):
    return {'format':'gold-collector','version':1,'posts':[{'key':'tester:123456','id':'123456','owner':'tester','author':'writer','text':text,'sources':sources or ['likes'],'url':'https://x.com/writer/status/123456','links':[],'media':[],'postedAt':'2024-01-01T00:00:00Z','status':'inbox','note':'','reasons':[]}]}

class WorkspaceTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.w=Workspace(self.tmp.name);self.w.import_backup(data=backup())
    def tearDown(self):self.w.close();self.tmp.cleanup()
    def test_idempotent_roundtrip_and_atomic_validation(self):
        self.assertTrue(self.w.import_backup(data=backup())['idempotent'])
        exported=self.w.export(format='backup');self.assertEqual(json.loads(pathlib.Path(exported['path']).read_text()),backup())
        invalid=backup();invalid['posts'].append({'bad':True})
        with self.assertRaises(ValueError):self.w.import_backup(data=invalid)
        self.assertEqual(self.w.revision(),1)
    def test_snapshots_and_result_sets_survive_updates(self):
        result=self.w.query('tutorial');rid=result['receipt']['result_id']
        self.w.import_backup(data=backup('Completely different text',['bookmarks']))
        self.assertEqual(self.w.query('tutorial')['receipt']['count'],0)
        self.assertEqual(self.w.query('tutorial',snapshot=1)['receipt']['count'],1)
        self.assertEqual(self.w.result(rid)['rows'][0]['text'],backup()['posts'][0]['text'])
        self.assertEqual(self.w.inventory()['posts'],1)
    def test_sql_cannot_write_or_attach(self):
        self.assertEqual(self.w.sql('SELECT count(*) AS n FROM current_posts')['rows'][0]['n'],1)
        for sql in ["DELETE FROM observations","ATTACH DATABASE ':memory:' AS evil","PRAGMA writable_schema=ON","SELECT load_extension('evil')"]:
            with self.assertRaises(Exception):self.w.sql(sql)
        self.assertEqual(self.w.inventory()['posts'],1)
    def test_full_text_and_resource_search(self):
        self.assertEqual(self.w.query('tutorial AND software',mode='fts')['receipt']['count'],1)
        self.assertEqual(self.w.sql('SELECT observation_id FROM observation_fts WHERE observation_fts MATCH ?',['tutorial'])['receipt']['count'],1)
        self.w._resource({'url':'https://example.com','text':'New linked evidence','raw':b'New linked evidence','extractor':'test','mime':'text/plain'})
        self.assertEqual(self.w.query('linked evidence',kind='resource')['receipt']['count'],1)
        self.assertEqual(self.w.query('linked evidence',kind='resource',snapshot=1)['receipt']['count'],0)
    def test_claim_span_validation_and_version_conflict(self):
        inv=self.w.investigate('Find learning resources')['id'];p=self.w.records()[0]
        e={'observation_id':p['observation_id'],'start':2,'end':10,'quote':'tutorial'}
        self.w.claim(inv,'claim','The author describes a tutorial',[e])
        with self.assertRaises(ValueError):self.w.claim(inv,'claim2','Fake',[{**e,'quote':'invented'}])
        with self.assertRaises(ValueError):self.w.artifact(inv,'claim','note',{},expected_version=0)
        self.assertEqual(self.w.read_artifact(inv,'claim')['version'],1)
    def test_resume_branch_and_reversible_merge(self):
        inv=self.w.investigate('Explore')['id'];self.w.artifact(inv,'findings','notes',{'a':1});self.w.close();self.w=Workspace(self.tmp.name)
        self.assertEqual(self.w.resume(inv)['artifacts'][0]['name'],'findings')
        branch=self.w.branch(inv,'Alternative')['id'];self.w.artifact(branch,'findings','notes',{'a':2})
        self.w.merge_artifact(branch,'findings',inv,'findings',1)
        self.assertEqual(self.w.read_artifact(inv,'findings',1)['content'],{'a':1})
        self.assertEqual(self.w.read_artifact(inv,'findings')['content']['artifact'],{'a':2})
    def test_jobs_checkpoint_cancel_resume_and_failures(self):
        j=self.w.create_job('fetch',['https://example.com/1','https://example.com/2'],'test')['id']
        self.assertEqual(j,self.w.create_job('fetch',['https://example.com/1','https://example.com/2'],'test')['id'])
        with patch.object(self.w,'_fetch_resource',return_value={'ok':True}) as fetch:
            self.assertEqual(self.w.run_job(j,1)['state'],'pending');self.w.cancel_job(j)
            self.assertEqual(self.w.run_job(j,1)['state'],'cancelled')
            self.assertEqual(self.w.run_job(j,1,resume=True)['state'],'completed');self.assertEqual(fetch.call_count,2)
        failed=self.w.create_job('fetch',['https://example.com/3'])['id']
        with patch.object(self.w,'_fetch_resource',side_effect=ValueError('HTTP 403')):
            self.assertEqual(self.w.run_job(failed)['state'],'failed')
        self.assertEqual(len(self.w.retry_job(failed)['payload']['items']),1)
    def test_live_lease_prevents_duplicate_workers(self):
        import time
        j=self.w.create_job('fetch',[])['id']
        with self.w.db:self.w.db.execute("UPDATE jobs SET state='running',progress=? WHERE id=?",(json.dumps({'cursor':0,'results':[],'errors':[],'lease_until':time.time()+100}),j))
        with self.assertRaises(ValueError):self.w.run_job(j)
    def test_resource_commit_survives_crash_before_cursor_checkpoint(self):
        j=self.w.create_job('fetch',['https://example.com'])['id']
        captured=self.w._resource({'url':'https://example.com','text':'Evidence','raw':b'Evidence','extractor':'test','mime':'text/plain'},j+':0')
        self.w.close();self.w=Workspace(self.tmp.name)
        with patch.object(self.w,'_fetch_resource',side_effect=AssertionError('Must reuse committed output')):
            done=self.w.run_job(j)
        self.assertEqual(done['state'],'completed')
        self.assertEqual(done['progress']['results'][0]['result'],captured)
        self.assertEqual(self.w.revision(),2)
    def test_public_fetch_rejects_private_destinations(self):
        for url in ['http://127.0.0.1/','http://169.254.169.254/','file:///C:/secret','https://user:pass@example.com/']:
            with self.assertRaises(ValueError):validate_url(url)
    def test_extraction_keeps_provenance_and_quote_offsets(self):
        path=pathlib.Path(self.tmp.name)/'transcript.txt';path.write_text('A supplied transcript.',encoding='utf-8');p=self.w.records()[0]
        j=self.w.create_job('extract_text',[{'path':str(path),'observation_id':p['observation_id'],'extractor':'test-transcript'}])['id']
        done=self.w.run_job(j);self.assertEqual(done['state'],'completed')
        resource=self.w.get([done['progress']['results'][0]['result']['observation_id']])[0]
        self.assertEqual(resource['raw']['source_observation'],p['observation_id']);self.assertEqual(resource['text'],'A supplied transcript.')
    def test_mcp_protocol_and_argument_validation(self):
        requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}},{'jsonrpc':'2.0','method':'notifications/initialized'},{'jsonrpc':'2.0','id':2,'method':'tools/list'},{'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'inventory','arguments':{}}},{'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'query','arguments':{'snapshot':'not-a-number'}}}]
        output=subprocess.check_output([sys.executable,str(ROOT/'scripts/workspace.py'),'--workspace',self.tmp.name,'mcp'],input='\n'.join(json.dumps(r) for r in requests).encode())
        responses=[json.loads(line) for line in output.splitlines()];self.assertEqual(len(responses),4);self.assertEqual(responses[0]['result']['protocolVersion'],'2024-11-05');self.assertFalse(responses[2]['result']['isError']);self.assertTrue(responses[3]['result']['isError'])

if __name__=='__main__':unittest.main()
