import unittest,tempfile,json
from unittest.mock import patch
from gold_workspace import Workspace
from gold_workspace.enrichment import plan,process_asset
from test_workspace import backup
class EnrichmentTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.w=Workspace(self.tmp.name)
 def tearDown(self):self.w.close();self.tmp.cleanup()
 def test_duplicate_assets_share_evidence_and_remain_searchable(self):
  b=backup();b['posts'][0]['links']=['https://example.com/guide'];second={**b['posts'][0],'id':'654321','key':'tester:654321'};b['posts'].append(second);self.w.import_backup(data=b)
  p=plan(self.w,shards=1);self.assertEqual(p['unique_assets'],1)
  with patch('gold_workspace.fetching.fetch_bytes',return_value={'raw':b'Hidden attachment knowledge','mime':'text/plain','url':'https://example.com/guide'}):
   j=self.w.run_job(p['jobs'][0]);self.assertEqual(j['state'],'completed')
  result=self.w.attachment_query('Hidden attachment');self.assertEqual(result['receipt']['count'],2)
  with patch('gold_workspace.fetching.fetch_bytes',side_effect=AssertionError('Cached asset must not fetch again')):
   self.assertTrue(process_asset(self.w,{'url':'https://example.com/guide'})['cached'])
 def test_multiple_assets_are_distinct_observations(self):
  self.w.import_backup(data=backup());source=self.w.records()[0]['observation_id']
  for url in ['https://example.com/1','https://example.com/2']:
   self.w._resource({'raw':b'evidence','text':'evidence','source_observation':source,'object_key':'asset:'+url,'url':url,'extractor':'test'})
  self.assertEqual(len(self.w.records(kind='resource')),2)
 def test_failed_extraction_remains_explicit(self):
  b=backup();b['posts'][0]['links']=['https://example.com/blocked'];self.w.import_backup(data=b);p=plan(self.w,shards=1)
  with patch('gold_workspace.fetching.fetch_bytes',side_effect=ValueError('HTTP 403')):self.assertEqual(self.w.run_job(p['jobs'][0])['state'],'failed')
  r=self.w.attachment_query();row=self.w.result(r['receipt']['result_id'])['rows'][0];self.assertEqual(row['attachments'][0]['coverage'],'not_extracted')
 def test_visual_interpretation_is_separate_and_searchable(self):
  b=backup();b['posts'][0]['links']=['https://example.com/image'];self.w.import_backup(data=b);plan(self.w,shards=1)
  r=self.w._resource({'raw':b'image','text':'OCR words','url':'https://example.com/image','source_url':'https://example.com/image','mime':'image/png','extractor':'fixture','coverage':'ocr_only'})
  with self.w.db:self.w.db.execute('INSERT INTO asset_cache VALUES(?,?)',('https://example.com/image',r['observation_id']))
  self.w.annotate_asset(r['observation_id'],'A diagram linking two processes',['Interpretation is uncertain'])
  self.assertEqual(self.w.get([r['observation_id']])[0]['text'],'OCR words')
  self.assertEqual(self.w.attachment_query('two processes')['receipt']['count'],1)
 def test_video_page_navigation_is_not_indexed_as_transcript(self):
  b=backup();b['posts'][0]['links']=['https://youtu.be/example'];self.w.import_backup(data=b);plan(self.w,shards=1)
  r=self.w._resource({'raw':b'footer','text':'Misleading video footer','url':'https://www.youtube.com/watch?v=example','source_url':'https://youtu.be/example','mime':'text/html','extractor':'fixture','coverage':'html_text_only'})
  with self.w.db:self.w.db.execute('INSERT INTO asset_cache VALUES(?,?)',('https://youtu.be/example',r['observation_id']))
  self.assertEqual(self.w.attachment_query('Misleading video footer')['receipt']['count'],0)
if __name__=='__main__':unittest.main()
