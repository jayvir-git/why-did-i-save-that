const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
function setup(count,token='paired-token') {
  const state={workspaceToken:token},calls=[];
  const context=vm.createContext({AbortSignal,Date,JSON,Error,
    chrome:{storage:{local:{get:async()=>({...state}),set:async v=>Object.assign(state,v)}},alarms:{onAlarm:{addListener(){}}}},
    getPosts:async()=>Array.from({length:count},(_,i)=>({id:String(i)})),
    fetch:async(url,options)=>{calls.push({url,...options});return {ok:true,json:async()=>({revision:calls.length})};}
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../extension/workspace-sync.js'),'utf8'),context);
  return {state,calls,context,run:()=>vm.runInContext('syncWorkspace()',context)};
}
test('workspace sync sends every post in bounded authenticated batches',async()=>{
  const t=setup(453);await Promise.all([t.run(),t.run()]);
  assert.deepEqual(t.calls.map(c=>JSON.parse(c.body).posts.length),[200,200,53]);
  assert.ok(t.calls.every(c=>c.url==='http://127.0.0.1:8766/ingest'&&c.headers.Authorization==='Bearer paired-token'));
  assert.equal(t.state.workspaceSyncStatus.posts,453);
});
test('workspace sync needs pairing and recovers from an unavailable bridge',async()=>{
  const t=setup(1,undefined);delete t.state.workspaceToken;await t.run();assert.equal(t.calls.length,0);
  t.state.workspaceToken='paired-token';const original=t.context.fetch;
  t.context.fetch=async()=>{throw new Error('offline');};await assert.rejects(t.run(),/offline/);
  assert.equal(t.state.workspaceSyncStatus.ok,false);
  t.context.fetch=original;await t.run();assert.equal(t.state.workspaceSyncStatus.ok,true);
});
test('disconnect stops subsequent sync batches',async()=>{
  const t=setup(453),original=t.context.fetch;
  t.context.fetch=async(...args)=>{const value=await original(...args);delete t.state.workspaceToken;return value;};
  await t.run();assert.equal(t.calls.length,1);
});
