import io
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from gold_workspace import Workspace
from gold_workspace.runner import failure, run_codex
from test_workspace import backup


class Process:
    def __init__(self, events, code=0):
        self.stdin=io.StringIO();self.stdout=io.StringIO('\n'.join(json.dumps(e) if isinstance(e,dict) else e for e in events)+'\n');self.code=code;self.killed=False
    def poll(self):return self.code
    def wait(self,timeout=None):return self.code
    def kill(self):self.killed=True


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.w=Workspace(self.tmp.name)
        self.w.import_backup(data=backup('Evidence for the review.'))
        self.oid=self.w.records()[0]['observation_id']
    def tearDown(self):self.w.close();self.tmp.cleanup()
    def test_atomic_note_replay_after_response_loss_and_payload_conflict(self):
        first=self.w.save_note('request-note-1','Finding','Useful evidence')
        self.assertEqual(self.w.save_note('request-note-1','Finding','Useful evidence'),first)
        self.assertEqual(self.w.action_outcome('request-note-1')['result'],first)
        self.assertEqual(self.w.db.execute('SELECT count(*) FROM investigations').fetchone()[0],1)
        with self.assertRaises(ValueError):self.w.save_note('request-note-1','Changed','Other content')
        self.assertEqual(self.w.db.execute('SELECT count(*) FROM artifacts').fetchone()[0],1)
    def test_concurrent_save_retries_commit_once(self):
        barrier=threading.Barrier(2);results=[];errors=[]
        def save():
            other=Workspace(self.tmp.name)
            try:barrier.wait();results.append(other.save_note('concurrent-save','Finding','Same content'))
            except Exception as error:errors.append(error)
            finally:other.close()
        threads=[threading.Thread(target=save) for _ in range(2)]
        for t in threads:t.start()
        for t in threads:t.join(5)
        self.assertFalse(errors);self.assertEqual(len(results),2);self.assertEqual(results[0],results[1])
        self.assertEqual(self.w.db.execute('SELECT count(*) FROM artifacts').fetchone()[0],1)
    def test_invalid_citation_does_not_leave_an_empty_investigation(self):
        with self.assertRaises(ValueError):self.w.save_note('invalid-evidence','Claim','Text',[{'observation_id':self.oid,'start':0,'end':4,'quote':'fake'}])
        self.assertEqual(self.w.db.execute('SELECT count(*) FROM investigations').fetchone()[0],0)
        self.assertEqual(self.w.action_outcome('invalid-evidence')['state'],'not_found')
    def test_review_completion_and_receipt_are_replayable(self):
        req=self.w.queue_review('queue-request-1',self.oid,'Explain')
        self.assertEqual(self.w.queue_review('queue-request-1',self.oid,'Explain'),req)
        before=self.w.revision()
        first=self.w.save_review('review-request-1',req['id'],'New transcript evidence',kind='transcript')
        self.assertEqual(self.w.save_review('review-request-1',req['id'],'New transcript evidence',kind='transcript'),first)
        self.assertEqual(self.w.revision(),before+1)
        self.assertEqual(self.w.get([self.oid])[0]['text'],'Evidence for the review.')
        self.assertEqual(self.w.search_library('transcript',mode='keyword')['receipt']['count'],1)
    def test_targets_include_every_reference_and_no_automatic_selection(self):
        data=backup('Several attachments');data['posts'][0]['links']=['https://example.com/a','https://example.com/b'];self.w.import_backup(data=data)
        oid=self.w.records()[0]['observation_id'];targets=self.w.source_targets(oid)['targets']
        self.assertEqual(len(targets),3);self.assertTrue(targets[0]['can_review']);self.assertFalse(targets[1]['can_review'])
        with patch('gold_workspace.runner.launch'):
            with self.assertRaises(ValueError):self.w.start_work('bad-extraction','extract',json.dumps({'observation_id':oid,'url':'https://unrelated.example','role':'link'}))
    def test_run_dedup_cancel_and_stale_heartbeat(self):
        req=self.w.queue_review('queue-request-1',self.oid,'Explain')
        with patch('gold_workspace.runner.launch'):
            a=self.w.start_work('start-request-1','review',req['id']);b=self.w.start_work('start-request-2','review',req['id'])
        self.assertEqual(a['id'],b['id'])
        self.w.cancel_work(a['id']);self.assertEqual(self.w.work_status(a['id'])['runs'][0]['state'],'cancelled')
        with patch('gold_workspace.runner.launch'):c=self.w.start_work('start-request-3','review',req['id'])
        with self.w.db:self.w.db.execute('UPDATE work_runs SET heartbeat=0 WHERE id=?',(c['id'],))
        self.assertEqual(self.w.work_status(c['id'])['runs'][0]['state'],'interrupted')
    def create_run(self):
        req=self.w.queue_review('queue-request-1',self.oid,'Explain')
        with patch('gold_workspace.runner.launch'):return self.w.start_work('start-request-1','review',req['id'])
    def test_codex_json_events_produce_draft_not_published_evidence(self):
        run=self.create_run();before=self.w.revision();calls=[]
        result={'description':'A bounded interpretation','uncertainties':['Only captured text'],'coverage_sufficient':True}
        events=[{'type':'thread.started'},{'type':'turn.started'},{'type':'error','message':'Transient reconnect'},{'type':'item.completed','item':{'type':'agent_message','text':json.dumps(result)}},{'type':'turn.completed'}]
        def launch(args,**kwargs):calls.append(args);return Process(events)
        with patch('gold_workspace.runner.shutil.which',return_value='codex'):run_codex(self.w,run,popen=launch)
        saved=self.w.work_status(run['id'])['runs'][0]
        self.assertEqual(saved['state'],'ready');self.assertEqual(saved['result'],result);self.assertEqual(self.w.revision(),before)
        self.assertIn('read-only',calls[0]);self.assertIn('--ignore-user-config',calls[0])
    def test_quota_and_auth_are_blocked_not_success(self):
        run=self.create_run()
        with patch('gold_workspace.runner.shutil.which',return_value='codex'):
            with self.assertRaisesRegex(RuntimeError,'usage limit'):run_codex(self.w,run,popen=lambda *a,**k:Process([{'type':'turn.failed','error':{'message':'Codex usage limit reached'}}],1))
        self.assertEqual(failure('Codex usage limit reached')[0],'blocked')
        self.assertEqual(failure('401 unauthorized')[0],'blocked')
    def test_worker_persists_provider_failure_for_reload(self):
        from gold_workspace.runner import _worker
        run=self.create_run()
        with patch('gold_workspace.runner.run_codex',side_effect=RuntimeError('Codex usage limit reached')):
            _worker(self.w.path,run['id'],('test',run['id']))
        other=Workspace(self.tmp.name)
        try:
            saved=other.work_status(run['id'])['runs'][0]
            self.assertEqual(saved['state'],'blocked');self.assertIn('reset',saved['message'])
        finally:other.close()
    def test_cancelled_run_cannot_publish_a_late_result(self):
        from gold_workspace.runner import update
        run=self.create_run();self.w.cancel_work(run['id'])
        self.assertFalse(update(self.w,run['id'],'ready','Late response',{'description':'Too late'}))
        self.assertEqual(self.w.work_status(run['id'])['runs'][0]['state'],'cancelled')
    def test_actions_require_outcomes_and_check_versions(self):
        a=self.w.save_source_action('planned-action-1',self.oid,next_action='Try the technique')
        with self.assertRaises(ValueError):self.w.save_source_action('complete-action-1',self.oid,next_action='Try the technique',state='done',expected_version=1)
        b=self.w.save_source_action('complete-action-2',self.oid,next_action='Try the technique',state='done',outcome='Built a working example',expected_version=1)
        self.assertEqual(b['version'],2)
        self.assertEqual(self.w.save_source_action('complete-action-2',self.oid,next_action='Try the technique',state='done',outcome='Built a working example',expected_version=1),b)
        with self.assertRaises(ValueError):self.w.save_source_action('old-action-edit',self.oid,next_action='Another task',expected_version=1)
    def test_status_tokens_detect_changes_but_not_result_reads(self):
        before=self.w.workspace_status();self.w.search_library('',mode='keyword');same=self.w.workspace_status()
        self.assertEqual(before['sources_token'],same['sources_token']);self.assertEqual(before['notes_token'],same['notes_token'])
        self.w.save_note('request-note-1','New note','My finding')
        after=self.w.workspace_status();self.assertNotEqual(before['notes_token'],after['notes_token'])

if __name__=='__main__':unittest.main()
