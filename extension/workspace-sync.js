/* Background-only local sync. The page cannot read the pairing token or choose URLs. */
const WORKSPACE_ORIGIN='http://127.0.0.1:8766';
let workspaceSyncPromise;
async function syncWorkspace(){
  if(workspaceSyncPromise)return workspaceSyncPromise;
  workspaceSyncPromise=(async()=>{
    const {workspaceToken}=await chrome.storage.local.get('workspaceToken');
    if(!workspaceToken)return {connected:false};
    const posts=await getPosts();
    let result={revision:0};
    for(let offset=0;offset<posts.length;offset+=200){
      const current=await chrome.storage.local.get('workspaceToken');if(current.workspaceToken!==workspaceToken)return {connected:false};
      const response=await fetch(WORKSPACE_ORIGIN+'/ingest',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+workspaceToken},body:JSON.stringify({format:'gold-collector',version:1,posts:posts.slice(offset,offset+200)}),signal:AbortSignal.timeout(20000)});
      if(!response.ok)throw new Error(`Local workspace returned ${response.status}`);result=await response.json();
    }
    await chrome.storage.local.set({workspaceSyncStatus:{ok:true,time:new Date().toISOString(),posts:posts.length,revision:result.revision}});return result;
  })();
  try{return await workspaceSyncPromise;}catch(e){await chrome.storage.local.set({workspaceSyncStatus:{ok:false,time:new Date().toISOString(),error:e.message}});throw e;}finally{workspaceSyncPromise=null;}
}
chrome.alarms.onAlarm.addListener(alarm=>{if(alarm.name==='workspace-sync')syncWorkspace().catch(()=>{});});
