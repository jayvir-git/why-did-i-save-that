const {test}=require('node:test');const assert=require('node:assert/strict');const c=require('../extension/core.js');
const raw={id:'123456789',owner:'Tester',author:'someone',text:'A post',sources:['likes'],capture:'visible',partial:true};
test('video variants survive normalization and thumbnail-only recapture',()=>{
  const p=c.normalize({...raw,media:[{type:'video',url:'https://pbs.twimg.com/thumb.jpg',durationMs:1000,variants:[{url:'https://video.twimg.com/a.mp4',contentType:'video/mp4',bitrate:256000},{url:'javascript:evil()',contentType:'video/mp4'}]}]});
  assert.equal(p.media[0].variants.length,1);assert.equal(p.media[0].durationMs,1000);
  const merged=c.merge(p,c.normalize({...raw,media:[{type:'video',url:'https://pbs.twimg.com/thumb.jpg'}]}));
  assert.equal(merged.media[0].variants[0].url,'https://video.twimg.com/a.mp4');assert.equal(merged.media[0].durationMs,1000);
});
test('normalization rejects invalid IDs/accounts and unsafe URLs',()=>{
  assert.equal(c.normalize({...raw,id:'<script>'}),null);assert.equal(c.normalize({...raw,owner:'../user'}),null);
  assert.equal(c.normalize({...raw,owner:undefined}),null);assert.equal(c.normalize({...raw,id:123456789}),null);
  const p=c.normalize({...raw,links:['javascript:alert(1)','https://example.com','file:///secret']});
  assert.deepEqual(p.links,['https://example.com/']);assert.equal(p.key,'tester:123456789');
});
test('recapture merges likes + bookmarks, upgrades text, and preserves review decisions',()=>{
  const p={...c.normalize(raw,'2026-01-01T00:00:00Z'),note:'For my project',reasons:['Learning'],status:'kept'};
  const newer=c.normalize({...raw,text:'Full post from network',capture:'network',partial:false,sources:['bookmarks']},'2026-02-01T00:00:00Z');
  const merged=c.merge(p,newer);assert.deepEqual(merged.sources,['likes','bookmarks']);assert.equal(merged.note,p.note);assert.equal(merged.status,'kept');assert.equal(merged.text,newer.text);assert.equal(merged.firstCollectedAt,p.firstCollectedAt);
  assert.equal(c.merge(merged,c.normalize(raw)).text,newer.text);
});
test('network parser captures roots, not quoted posts or promoted items',()=>{
  const tweet=(id,text)=>({rest_id:id,legacy:{full_text:text,created_at:'2026-01-01',entities:{urls:[]}},core:{user_results:{result:{core:{screen_name:'author',name:'Author'}}}}});
  const main=tweet('123456','Short');main.note_tweet={note_tweet_results:{result:{text:'Full long post'}}};main.quoted_status_result={result:tweet('654321','Quoted')};
  const data={data:{timeline:{instructions:[{entries:[{content:{itemContent:{tweet_results:{result:main}}}},{content:{itemContent:{promotedMetadata:{},tweet_results:{result:tweet('999999','Ad')}}}}]}]}}};
  const result=c.extractTimeline(data,'bookmarks','tester');assert.equal(result.length,1);assert.equal(result[0].text,'Full long post');assert.equal(result[0].quotedPost.id,'654321');
});
test('only known history routes and GraphQL operations are eligible',()=>{
  assert.equal(c.sourceFromPath('/i/history/likes'),'likes');assert.equal(c.sourceFromPath('/i/history'),'bookmarks');assert.equal(c.sourceFromPath('/home'),null);
  assert.equal(c.operationSource('https://x.com/i/api/graphql/abc/Likes'),'likes');
  assert.equal(c.operationSource('https://evil.example/i/api/graphql/abc/Likes'),null);
  assert.equal(c.operationSource('https://x.com/i/api/graphql/abc/HomeTimeline'),null);
});
test('same post in two accounts remains separate',()=>{assert.notEqual(c.normalize(raw).key,c.normalize({...raw,owner:'other'}).key);});
