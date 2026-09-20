// Optional connection: explicit button gesture requests only the fixed loopback origin.
const workspacePanel=document.createElement('details');workspacePanel.className='queue-help';
workspacePanel.innerHTML='<summary>Agent workspace connection</summary><p>Start the local bridge, then paste its pairing token. Posts synchronize to this computer only.</p><label>Pairing token <input id="workspace-token" type="password" autocomplete="off"></label><button id="workspace-connect" class="button secondary">Connect and sync</button><button id="workspace-disconnect" class="button secondary">Disconnect</button><p id="workspace-status" role="status"></p>';
if(globalThis.chrome?.runtime?.id)document.querySelector('header').after(workspacePanel);
const workspaceStatus=workspacePanel.querySelector('#workspace-status');
workspacePanel.querySelector('#workspace-connect').onclick=async()=>{
  try{
    const token=workspacePanel.querySelector('input').value.trim();if(!token)throw new Error('Enter the token from workspace-data/bridge-token.txt');
    const allowed=await chrome.permissions.request({origins:['http://127.0.0.1/*']});if(!allowed)throw new Error('Local connection permission was not granted.');
    const reply=await chrome.runtime.sendMessage({type:'workspace-connect',token});if(!reply?.ok)throw new Error(reply?.error||'Connection failed');
    workspacePanel.querySelector('input').value='';workspaceStatus.textContent='Connected and synchronized. Automatic sync runs every minute while Chrome is open.';
  }catch(e){workspaceStatus.textContent=e.message;}
};
workspacePanel.querySelector('#workspace-disconnect').onclick=async()=>{const reply=await chrome.runtime.sendMessage({type:'workspace-disconnect'});workspaceStatus.textContent=reply?.ok?'Disconnected; previously synchronized records remain local.':reply?.error;};
if(globalThis.chrome?.runtime?.id)chrome.storage.local.get('workspaceSyncStatus').then(({workspaceSyncStatus:s})=>{if(s)workspaceStatus.textContent=s.ok?`Last sync: ${s.time} · ${s.posts} posts`:`Last sync failed: ${s.error}`;});
