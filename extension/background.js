importScripts('core.js', 'db.js');
// Pairing credentials are available only to extension pages and the worker.
chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'});
importScripts('workspace-sync.js');
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  (async () => {
    const isLibrary = sender.url === chrome.runtime.getURL('library.html') || sender.url === chrome.runtime.getURL('popup.html');
    const isX = sender.tab?.id !== undefined && sender.url?.startsWith('https://x.com/');
    if (!isLibrary && !isX) throw new Error('Unrecognized sender');
    if(message.type==='workspace-connect'&&isLibrary){
      if(typeof message.token!=='string'||message.token.length<20||message.token.length>200)throw new Error('Invalid pairing token');
      await chrome.storage.local.set({workspaceToken:message.token});await chrome.alarms.create('workspace-sync',{periodInMinutes:1});return await syncWorkspace();
    }
    if(message.type==='workspace-disconnect'&&isLibrary){await chrome.alarms.clear('workspace-sync');await chrome.storage.local.remove(['workspaceToken','workspaceSyncStatus']);return true;}
    const sessionKey = `collect:${sender.tab?.id}`;
    if(message.type==='collection-progress'&&isX){
      const state=(await chrome.storage.session.get(sessionKey))[sessionKey]||{enabled:false,added:0};
      const j=message.job;
      if(!j||!['likes','bookmarks'].includes(j.source)||!['running','paused','exhausted_visible'].includes(j.state))throw new Error('Invalid collection checkpoint');
      await chrome.storage.session.set({[sessionKey]:{...state,job:{source:j.source,state:j.state,steps:Number(j.steps)||0,lastPost:String(j.lastPost||'').slice(0,30),updated:new Date().toISOString()}}});return true;
    }
    if (message.type === 'state' && isX) return (await chrome.storage.session.get(sessionKey))[sessionKey] || {enabled:false, added:0};
    if (message.type === 'enabled' && isX) {
      const previous = (await chrome.storage.session.get(sessionKey))[sessionKey] || {added:0};
      const state = {...previous, enabled:message.enabled === true};
      await chrome.storage.session.set({[sessionKey]:state}); return state;
    }
    if (message.type === 'capture' && isX) {
      const state = (await chrome.storage.session.get(sessionKey))[sessionKey];
      if (!state?.enabled) return {added:0, paused:true};
      if (!Array.isArray(message.posts) || message.posts.length > 200) throw new Error('Invalid capture batch');
      const posts = message.posts.map(p => GoldCore.normalize(p)).filter(Boolean);
      const result = await savePosts(posts);
      // Counts are informational; post writes themselves are transactional.
      const current = (await chrome.storage.session.get(sessionKey))[sessionKey] || state;
      await chrome.storage.session.set({[sessionKey]:{...current, added:(current.added || 0) + result.added}});
      return result;
    }
    if (message.type === 'library') { await chrome.tabs.create({url:chrome.runtime.getURL('library.html')}); return true; }
    throw new Error('Unsupported request');
  })().then(value => reply({ok:true,value})).catch(error => reply({ok:false,error:error.message}));
  return true;
});
chrome.tabs.onRemoved.addListener(id => chrome.storage.session.remove(`collect:${id}`));
