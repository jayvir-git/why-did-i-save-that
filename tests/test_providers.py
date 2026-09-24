import io
import json
import tempfile
import unittest
from unittest.mock import patch

from gold_workspace import Workspace
from gold_workspace.runner import run_claude, failure, _worker
from test_workspace import backup
from test_workflows import Process


class Input(io.StringIO):
    def close(self): self.sent=self.getvalue();super().close()


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.w=Workspace(self.temp.name)
        self.w.import_backup(data=backup('Only this selected captured text.'))
        self.oid=self.w.records()[0]['observation_id']
        self.request=self.w.queue_review('queue-provider-test',self.oid,'Explain the evidence')
    def tearDown(self):self.w.close();self.temp.cleanup()
    def start(self, provider='claude', key='start-provider-test'):
        with patch('gold_workspace.runner.launch'):return self.w.start_work(key,'review',self.request['id'],provider)
    def test_provider_persists_and_cross_provider_active_runs_deduplicate(self):
        run=self.start()
        self.assertEqual(run['provider'],'claude')
        again=self.start('codex','another-provider-test')
        self.assertEqual(again['id'],run['id']);self.assertEqual(again['provider'],'claude')
        self.w.cancel_work(run['id'])
        with self.assertRaises(ValueError):self.start('codex')
        fresh=self.start('codex','new-provider-test')
        self.assertEqual(fresh['provider'],'codex')
        other=Workspace(self.temp.name)
        try:self.assertEqual(other.work_status(run['id'])['runs'][0]['provider'],'claude')
        finally:other.close()
    def test_legacy_run_defaults_to_codex_and_unknown_provider_rejected(self):
        run=self.start('codex')
        with self.w.db:self.w.db.execute('DELETE FROM work_run_providers WHERE run_id=?',(run['id'],))
        self.assertEqual(self.w.work_status(run['id'])['runs'][0]['provider'],'codex')
        with self.assertRaises(ValueError):self.start('unrecognized')
    def test_claude_stream_requires_structured_success_and_has_no_tools(self):
        run=self.start();before=self.w.revision()
        result={'description':'Selected evidence only','uncertainties':['No linked page'],'coverage_sufficient':False}
        process=Process([{'type':'system','subtype':'init'},{'type':'result','subtype':'success','is_error':False,'structured_output':result}]);process.stdin=Input();calls=[]
        def spawn(args,**kwargs):calls.append((args,kwargs));return process
        with patch('gold_workspace.runner.shutil.which',return_value='claude.exe'):run_claude(self.w,run,popen=spawn)
        saved=self.w.work_status(run['id'])['runs'][0]
        self.assertEqual(saved['state'],'ready');self.assertEqual(saved['result'],result);self.assertEqual(before,self.w.revision())
        args,kwargs=calls[0]
        self.assertEqual(args[args.index('--tools')+1],'');self.assertIn('--safe-mode',args);self.assertIn('--strict-mcp-config',args)
        self.assertIn('--no-session-persistence',args);self.assertNotIn('--dangerously-skip-permissions',args)
        self.assertNotEqual(kwargs['cwd'],str(self.w.path))
        sent=json.loads(process.stdin.sent)
        self.assertEqual(sent['type'],'user');self.assertIn('Only this selected',sent['message']['content'][0]['text'])
    def test_claude_image_is_sent_as_selected_base64_input(self):
        raw=b'fixture image bytes'
        image=self.w._resource({'raw':raw,'text':'','mime':'image/png','coverage':'image','url':'https://example.com/image.png','extractor':'fixture'})
        self.request=self.w.queue_review('queue-image-test',image['observation_id'],'Describe')
        run=self.start();process=Process([{'type':'result','subtype':'success','structured_output':{'description':'Image draft','uncertainties':[],'coverage_sufficient':True}}]);process.stdin=Input()
        with patch('gold_workspace.runner.shutil.which',return_value='claude.exe'):run_claude(self.w,run,popen=lambda *a,**k:process)
        block=json.loads(process.stdin.sent)['message']['content'][1]
        import base64
        self.assertEqual(base64.b64decode(block['source']['data']),raw)
        self.assertEqual(block['source']['media_type'],'image/png')
    def test_failure_timeout_and_malformed_results_never_become_ready(self):
        for event,pattern in [({'type':'result','subtype':'error_during_execution','is_error':True,'errors':['usage limit reached']},'usage limit'),
                              ({'type':'result','subtype':'success','structured_output':{}},'expected format'),
                              ({'type':'system','subtype':'init'},'successful completion')]:
            with self.subTest(event=event):
                run=self.start(key='test-'+str(len(self.w.work_status()['runs']))+'-attempt')
                with patch('gold_workspace.runner.shutil.which',return_value='claude.exe'):
                    with self.assertRaisesRegex((RuntimeError,ValueError),pattern):run_claude(self.w,run,popen=lambda *a,**k:Process([event]))
                self.w.cancel_work(run['id'])
        run=self.start(key='timeout-test-attempt')
        with patch('gold_workspace.runner.shutil.which',return_value='claude.exe'):
            with self.assertRaises(TimeoutError):run_claude(self.w,run,popen=lambda *a,**k:Process([]),timeout=0)
        self.assertNotEqual(self.w.work_status(run['id'])['runs'][0]['state'],'ready')
    def test_worker_dispatches_claude_and_names_its_recovery(self):
        run=self.start()
        with patch('gold_workspace.runner.run_claude',side_effect=RuntimeError('usage limit reached')) as claude, patch('gold_workspace.runner.run_codex') as codex:
            _worker(self.w.path,run['id'],('test',run['id']))
        claude.assert_called_once();codex.assert_not_called()
        saved=self.w.work_status(run['id'])['runs'][0]
        self.assertEqual(saved['state'],'blocked');self.assertIn('Claude Code',saved['message']);self.assertNotIn('Codex',saved['message'])
        self.assertIn('claude auth login',failure('401 unauthorized','claude')[1])
