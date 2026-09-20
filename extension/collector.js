(() => {
  'use strict';
  const core = GoldCore;
  let enabled = false, added = 0, source = null, owner = '', host, root, observer;
  let busy = false, rescan = false, networkCount = 0, visibleCount = 0, lastPath = '', autoTimer, steps = 0, staleSteps = 0, lastCount = 0;
  let error = '', seen = new Map(), queue = [], lastSaved = '', scrollJob = null;
  const send = async message => {
    const response = await chrome.runtime.sendMessage(message);
    if (!response?.ok) throw new Error(response?.error || 'Extension unavailable; reload this tab.');
    return response.value;
  };
  function account() {
    const href = document.querySelector('a[data-testid="AppTabBar_Profile_Link"]')?.getAttribute('href');
    return href?.match(/^\/([a-zA-Z0-9_]+)$/)?.[1] || '';
  }
  function control() { window.postMessage({channel:'gold-control-v1',enabled:enabled && !!source && !!owner}, location.origin); }
  function checkpoint(state='paused') {
    if(!source)return;
    const articles=[...document.querySelectorAll('main article[data-testid="tweet"]')];
    const lastPost=articles.at(-1)?.querySelector('time')?.closest('a')?.getAttribute('href')?.match(/status\/(\d+)/)?.[1]||'';
    scrollJob={source,state,steps,lastPost};send({type:'collection-progress',job:scrollJob}).catch(()=>{});
  }
  function stopScroll(state='paused') { if(autoTimer)checkpoint(state);clearInterval(autoTimer); autoTimer = null; render(); }
  function render() {
    if (!root) return;
    host.style.display = source ? 'block' : 'none';
    root.querySelector('#status').textContent = enabled ? 'Collecting as you browse' : 'Ready when you are';
    root.querySelector('#mode').textContent = `${source === 'likes' ? 'Likes' : 'Bookmarks'}${owner ? ` · @${owner}` : ''}`;
    root.querySelector('#count').textContent = String(added);
    root.querySelector('#detail').textContent = `${visibleCount} visible captures · ${networkCount} network captures`;
    root.querySelector('#toggle').textContent = enabled ? 'Pause collection' : 'Start collecting';
    root.querySelector('#auto').textContent = autoTimer ? 'Pause scrolling' : scrollJob?.state==='paused' ? 'Resume scrolling' : 'Scroll for me';
    root.querySelector('#auto').disabled = !enabled;
    root.querySelector('#hint').textContent = error || lastSaved || 'Stored in this Chrome profile. No uploads.';
    root.querySelector('#hint').style.color = error ? '#ad3636' : '#626269';
    root.querySelector('#led').style.background = enabled ? '#d5f23b' : '#c4c5be';
  }
  async function toggle() {
    try {
      owner = account();
      if (!owner) throw new Error('Cannot identify the signed-in account. Open your own History page and try again.');
      const state = await send({type:'enabled',enabled:!enabled});
      enabled = state.enabled; added = state.added || 0; error = '';
      if (!enabled) { queue = []; stopScroll(); } else seen.clear();
      control(); render(); if (enabled) scan();
    } catch (e) { error = e.message; render(); }
  }
  function mount() {
    if (!document.body || host) return;
    host = document.createElement('div'); host.id = 'gold-collector-panel';
    host.style.cssText = 'position:fixed;bottom:20px;right:20px;width:min(290px,calc(100vw - 40px));z-index:2147483647;';
    root = host.attachShadow({mode:'closed'});
    root.innerHTML = `<style>
      :host{all:initial}*{box-sizing:border-box}.panel{font:13px/1.5 system-ui,sans-serif;background:#fcfbf7;color:#22352e;border:1px solid #cdd8d0;border-radius:16px;padding:18px;box-shadow:0 6px 28px #0002}
      header{display:flex;align-items:center;justify-content:space-between}b{font-size:13px;letter-spacing:.04em}#led{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px}#mode{font-size:12px;color:#68736e;margin:5px 0}#count{font-size:34px;font-weight:600;line-height:1.2}small{color:#68736e}#detail,#hint{font-size:11px;margin:8px 0;overflow-wrap:anywhere}button{font:inherit;cursor:pointer;border:1px solid #d0d8d2;border-radius:8px;padding:8px 10px;background:white;color:#244d3e}button:hover{background:#ecf2ec}button:disabled{opacity:.45;cursor:default}#toggle{background:#245b46;color:white;width:100%;margin:8px 0}footer{display:flex;gap:8px}footer button{flex:1}#min{border:0;background:none;padding:0 4px}.compact #body{display:none}

      .panel{background:#fcfcfa;color:#222126;border:1px solid #95968f;border-top:3px solid #392c45;border-radius:2px;box-shadow:3px 3px 0 #0002;padding:16px}
      b{font-size:15px;letter-spacing:-.3px}.edition{font:9px Consolas,monospace;color:#626269;margin-left:6px;letter-spacing:.5px}
      #led{border:1px solid #62694c;width:8px;height:8px}#mode,small{color:#626269}#count{font-family:Consolas,monospace}
      #detail{padding-bottom:12px;border-bottom:2px dotted #a4a792}button{border-radius:2px;color:#392c45;border-color:#bfc1b7}button:hover{background:#edf0e3}
      #toggle{background:#392c45;border-color:#392c45;color:#fff}button:focus-visible{outline:2px solid #655078;outline-offset:3px}button:active:not(:disabled){transform:translateY(1px)}
      </style><section class="panel"><header><b><span id="led"></span>the inator. <span class="edition">COLLECTOR</span></b><button id="min" aria-label="Collapse collector">−</button></header><div id="body"><div id="mode"></div><div id="status"></div><div><span id="count">0</span> <small>new posts this session</small></div><div id="detail"></div><button id="toggle">Start collecting</button><footer><button id="auto">Scroll for me</button><button id="library">Open library</button></footer><div id="hint" role="status"></div></div></section>`;
    document.body.append(host);
    root.querySelector('#toggle').addEventListener('click', toggle);
    root.querySelector('#library').addEventListener('click', () => send({type:'library'}).catch(e => {error=e.message;render();}));
    root.querySelector('#min').addEventListener('click', () => {
      const compact = root.querySelector('section').classList.toggle('compact');
      root.querySelector('#min').textContent = compact ? '+' : '−';
      root.querySelector('#min').setAttribute('aria-label', compact ? 'Expand collector' : 'Collapse collector');
    });
    root.querySelector('#auto').addEventListener('click', () => {
      if (autoTimer) return stopScroll();
      steps = scrollJob?.steps||0; staleSteps = 0; lastCount = seen.size;checkpoint('running');
      autoTimer = setInterval(() => {
        if (!enabled || !source || document.hidden) { lastSaved='Scrolling paused. Keep this history tab visible to resume.';stopScroll(); return; }
        staleSteps = seen.size === lastCount ? staleSteps + 1 : 0; lastCount = seen.size;
        steps++;
        const atBottom=scrollY+innerHeight>=document.documentElement.scrollHeight-4;
        const loading=!!document.querySelector('main [role="progressbar"]');
        if (staleSteps >= 12 && atBottom && !loading && !busy && !queue.length) {
          lastSaved = 'No more posts loaded after repeated bottom checks. Available timeline collected; historical completeness is unknown.'; stopScroll('exhausted_visible'); return;
        }
        if(staleSteps>=30){lastSaved='No new posts are loading. Progress saved; resume after checking X.';stopScroll();return;}
        if(steps%3===0)checkpoint('running');
        window.scrollBy({top:Math.max(300,innerHeight * .7),behavior:'smooth'});
      }, 2300);
      render();
    });
    render();
  }
  function signature(p) { return JSON.stringify([p.id,p.owner,p.sources,p.text,p.context,p.partial,p.capture,p.links,p.media]); }
  function enqueue(posts) {
    for (const p of posts) {
      const sig = signature(p), key = `${p.owner}:${source}:${p.id}:${p.capture}`;
      if (seen.get(key) === sig) continue;
      if (queue.length < 1000) queue.push({p,key,sig});
    }
    flush();
  }
  async function flush() {
    if (busy || !queue.length || !enabled) return;
    busy = true;
    const batch = queue.splice(0,100);
    try {
      const result = await send({type:'capture', posts:batch.map(x => x.p)});
      if (!result.paused) {
        added += result.added;
        for (const x of batch) {seen.set(x.key,x.sig); if(x.p.capture === 'network') networkCount++; else visibleCount++;}
        error = ''; lastSaved = `Saved locally at ${new Date().toLocaleTimeString()}`;
      }
    } catch (e) {
      error = `Not saved: ${e.message}`; enabled = false; stopScroll(); control();
      send({type:'enabled',enabled:false}).catch(() => {});
    } finally { busy = false; render(); if (queue.length && enabled) flush(); }
  }
  function scan() {
    if (!enabled || !source || !owner) return;
    // History swaps routes before its old timeline is necessarily removed.
    // Require the matching timeline label to avoid relabeling old likes as bookmarks.
    const timelineLabel = source === 'likes' ? 'Timeline: Likes' : 'Timeline: Bookmarks';
    const timeline = document.querySelector(`main [aria-label="${timelineLabel}"]`);
    if (!timeline) return;
    const posts = Array.from(timeline.querySelectorAll('article[data-testid="tweet"]'))
      .map(a => GoldDOM.readArticle(a, owner, source)).filter(Boolean);
    enqueue(posts);
  }
  window.addEventListener('message', e => {
    if (e.source !== window || e.origin !== location.origin || !enabled || !owner || !source) return;
    const d = e.data;
    if (d?.channel !== 'gold-posts-v1' || d.source !== source || !Array.isArray(d.posts) || d.posts.length > 200) return;
    const posts = d.posts.map(p => core.normalize({...p,owner,sources:[source],capture:'network'})).filter(Boolean);
    enqueue(posts);
  });
  function tick() {
    const nextOwner = account(), nextSource = core.sourceFromPath(location.pathname);
    if (location.pathname !== lastPath || nextOwner !== owner) {
      stopScroll(); queue = []; seen.clear();
      // Never silently carry collection into a different signed-in account.
      if (owner && nextOwner !== owner) { enabled = false; send({type:'enabled',enabled:false}).catch(() => {}); }
      lastPath = location.pathname; owner = nextOwner; source = nextSource; control();
    }
    mount(); render(); scan();
  }
  async function init() {
    try { const state = await send({type:'state'}); enabled = state.enabled; added = state.added || 0;scrollJob=state.job?{...state.job,state:state.job.state==='running'?'paused':state.job.state}:null; } catch(e) { error=e.message; }
    tick();
    observer = new MutationObserver(() => {
      if (rescan) return; rescan = true;
      setTimeout(() => { rescan=false;tick(); }, 350);
    });
    observer.observe(document.body,{childList:true,subtree:true});
    setInterval(tick,2000);
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded',init,{once:true}); else init();
})();
