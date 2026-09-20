const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const root=path.join(__dirname,'..','extension');

test('both script worlds boot even when script URLs are deduplicated',()=>{
  const manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
  const loaded=new Set(),contexts={};
  for(const entry of manifest.content_scripts){
    const world=entry.world||'ISOLATED';
    function XHR(){} XHR.prototype.open=()=>{};XHR.prototype.send=()=>{};
    const context=contexts[world] ||= vm.createContext({
      window:{addEventListener(){},fetch:async()=>({})},
      document:{readyState:'loading',addEventListener(){}},
      location:{origin:'https://x.com',pathname:'/i/history'},
      XMLHttpRequest:XHR,URL,console
    });
    for(const file of entry.js){
      if(loaded.has(file))continue;
      loaded.add(file);
      assert.doesNotThrow(()=>vm.runInContext(fs.readFileSync(path.join(root,file),'utf8'),context,{filename:file}),`${world} startup must not depend on a file injected in another world`);
    }
  }
});
