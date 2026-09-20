const {test}=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');const core=require('../extension/core.js');
function setup(){
  const listeners={},messages=[];let calls=0;
  const tweet={rest_id:'12345678',legacy:{full_text:'Captured'},core:{user_results:{result:{core:{screen_name:'author'}}}}};
  const data={timeline:{instructions:[{entries:[{content:{itemContent:{tweet_results:{result:tweet}}}}]}]}};
  const response={ok:true,clone:()=>({json:async()=>data})};
  function XHR(){}XHR.prototype.open=function(){};XHR.prototype.send=function(){};
  const window={addEventListener:(k,fn)=>listeners[k]=fn,postMessage:data=>messages.push(data),fetch:async()=>{calls++;return response;}};
  const context={GoldCore:core,window,location:{origin:'https://x.com',pathname:'/i/history/likes'},XMLHttpRequest:XHR,URL,Reflect,WeakMap};
  vm.runInNewContext(fs.readFileSync(require.resolve('../extension/network.js'),'utf8'),context);
  const control=enabled=>listeners.message({source:window,origin:'https://x.com',data:{channel:'gold-control-v1',enabled}});
  return {window,messages,control,response,calls:()=>calls,context};
}
const wait=()=>new Promise(resolve=>setImmediate(resolve));
test('network observation preserves original response and captures only while enabled',async()=>{
  const s=setup();const url='https://x.com/i/api/graphql/hash/Likes';
  assert.equal(await s.window.fetch(url),s.response);await wait();assert.equal(s.messages.length,0);
  s.control(true);assert.equal(await s.window.fetch(url),s.response);await wait();assert.equal(s.messages.length,1);assert.equal(s.messages[0].posts[0].id,'12345678');
  s.control(false);await s.window.fetch(url);await wait();assert.equal(s.messages.length,1);assert.equal(s.calls(),3);
});
test('unrelated requests and mismatched timelines do not leak into collection',async()=>{
  const s=setup();s.control(true);await s.window.fetch('https://x.com/i/api/graphql/hash/HomeTimeline');await s.window.fetch('https://x.com/i/api/graphql/hash/Bookmarks');await wait();assert.equal(s.messages.length,0);
});
test('pause discards responses still in flight',async()=>{
  const s=setup();s.control(true);const pending=s.window.fetch('https://x.com/i/api/graphql/hash/Likes');s.control(false);await pending;await wait();assert.equal(s.messages.length,0);
});
