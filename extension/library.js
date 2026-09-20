'use strict';
let posts = [], view = 'all', page = 0;
const D=GoldDiscovery, discovery=new Map(), skipped=new Set();
let worker, indexing=false, indexJob=0, queryJob=0, queryVector=null, queryText='', searchTimer, lastUndo=null;
let cacheWrites=Promise.resolve();
const pageSize = 40, $ = s => document.querySelector(s);
const labels = {all:'All posts', bookmarks:'Bookmarks', likes:'Likes', inbox:'To review', kept:'Kept', dismissed:'Dismissed'};
function node(tag, cls, text) { const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n; }
function notice(text, bad=false) { $('#notice').textContent=text;$('#notice').style.color=bad?'#a23838':''; }
function date(value) { return value ? new Date(value).toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'}) : 'Date unavailable'; }
function link(label, url) {
  const a=node('a','',label);a.href=GoldCore.safeUrl(url);a.target='_blank';a.rel='noopener noreferrer';return a;
}
async function edit(p, changes) {
  await updatePost(p.key,changes);Object.assign(p,changes);stats();
}
async function decide(p,status){
  const previous=p.status;await edit(p,{status});lastUndo={p,previous};$('#undo').hidden=false;render();
}
function getWorker(){
  if(worker)return worker;
  worker=new Worker('discovery-worker.mjs',{type:'module'});
  worker.onerror=()=>{indexing=false;$('#index-status').textContent='Local model could not start. Reload and try Prepare library again.';$('#prepare').disabled=false;$('#stop-index').hidden=true;notice('The local model could not start. Exact words search is still available.',true);};
  worker.onmessage=({data})=>{
    if(data.type==='query'&&data.id===queryJob){queryVector=data.vector;render();return;}
    if(data.type==='error'){
      if(data.requestType==='index'&&data.id===indexJob){indexing=false;$('#prepare').disabled=false;$('#stop-index').hidden=true;$('#index-status').textContent=`Preparation stopped: ${data.error}. Saved progress can be resumed.`;}
      if(data.requestType==='query'&&data.id===queryJob){notice(`Meaning search unavailable: ${data.error}. You can still use Exact words.`,true);$('#posts').replaceChildren(node('p','empty','Meaning search could not start. Select Exact words to search without the model.'));}
      return;
    }
    if(data.id!==indexJob)return;
    if(data.type==='batch'){
      for(const r of data.records)discovery.set(r.key,r);
      cacheWrites=cacheWrites.then(()=>saveDiscovery(data.records)).catch(e=>notice(`Index could not be cached: ${e.message}`,true));
      $('#index-status').textContent=`Preparing privately on this computer: ${data.done.toLocaleString()} / ${data.total.toLocaleString()} remaining posts`;
      $('#index-progress').value=data.done;$('#index-progress').max=data.total;
    }
    if(data.type==='complete'){indexing=false;$('#prepare').disabled=false;$('#stop-index').hidden=true;indexStatus();render();}
  };
  return worker;
}
function indexStatus(){if(!indexing){const n=posts.filter(p=>discovery.get(p.key)?.fingerprint===D.fingerprint(p)).length;$('#index-status').textContent=`${n.toLocaleString()} / ${posts.length.toLocaleString()} posts ready for meaning search and category suggestions. Runs locally.`;$('#index-progress').max=Math.max(1,posts.length);$('#index-progress').value=n;}}
function prepare(){
  if(indexing)return;
  const pending=posts.filter(p=>discovery.get(p.key)?.fingerprint!==D.fingerprint(p));
  if(!pending.length){indexStatus();return;}
  indexing=true;indexJob++;$('#prepare').disabled=true;$('#stop-index').hidden=false;$('#index-status').textContent='Loading the local model. Your posts stay on this computer…';
  getWorker().postMessage({type:'index',id:indexJob,posts:pending});
}
function search(){
  clearTimeout(searchTimer);queryVector=null;queryText=$('#search').value.trim();queryJob++;page=0;
  if(!queryText||$('#search-mode').value==='exact'){render();return;}
  const id=queryJob;render();searchTimer=setTimeout(()=>{notice('Finding related posts locally…');getWorker().postMessage({type:'query',id,query:queryText});},350);
}
function action(label, fn, cls='button secondary') {
  const b=node('button',cls,label);
  b.onclick=async()=>{b.disabled=true;try{await fn();}catch(e){notice(e.message,true);}finally{b.disabled=false;}};return b;
}
function card(p) {
  const article=node('article','post'), head=node('div','post-header'), who=node('div');
  who.append(node('div','author',p.authorName || p.author || 'Unknown author'),node('div','handle',`@${p.author || 'unknown'} · ${date(p.postedAt)}`));
  const badges=node('div','badges');
  for(const s of p.sources)badges.append(node('span','badge',s));
  if(p.status==='kept')badges.append(node('span','badge kept','Kept'));
  badges.append(node('span','badge',p.capture==='network'?'Network capture':'Visible text'));
  if(p.partial)badges.append(node('span','badge','May be incomplete'));
  head.append(who,badges);article.append(head,node('div','post-text',p.text || 'No text captured. Open the original to view its media.'));
  if(view==='inbox')article.prepend(node('p','queue-why',D.priority(p,discovery.get(p.key),$('#reason').value).why));
  const suggested=(discovery.get(p.key)?.suggestions||[]).filter(s=>!p.reasons.includes(s.label)&&!(p.rejectedReasons||[]).includes(s.label));
  if(suggested.length){
    const box=node('div','suggestions');box.append(node('span','suggestions-title','Suggested categories'));
    for(const s of suggested){const chip=node('span','suggestion');chip.title=s.evidence;chip.append(action(`+ ${s.label}`,async()=>{await edit(p,{reasons:[...new Set([...p.reasons,s.label])]});render();},'suggestion-accept'),action(`×`,async()=>{await edit(p,{rejectedReasons:[...new Set([...(p.rejectedReasons||[]),s.label])]});render();},'suggestion-reject'));chip.lastChild.setAttribute('aria-label',`Reject ${s.label} suggestion`);box.append(chip);}article.append(box);
  }
  if(p.context)article.append(node('div','context',p.context));
  if(p.quotedPost){const q=node('div','context');q.append(node('p','',`Quoted @${p.quotedPost.author || 'unknown'}: ${p.quotedPost.text}`),link('View quoted post ↗',`https://x.com/i/status/${p.quotedPost.id}`));article.append(q);}
  const links=node('div','post-links');
  for(const url of p.links.slice(0,8)){let host;try{host=new URL(url).hostname;}catch{continue;}links.append(link(host,url));}
  p.media.forEach((m,i)=>{const a=link(`${m.type==='photo'?'Image':'Media preview'} ${i+1} ↗`,m.url);a.title=m.alt;links.append(a);});
  if(links.childNodes.length)article.append(links);
  const reasons=node('div','reasons');reasons.setAttribute('aria-label','Why keep this post?');
  for(const reason of GoldCore.reasons){
    const b=action(reason,async()=>{
      const selected=p.reasons.includes(reason)?p.reasons.filter(r=>r!==reason):[...p.reasons,reason];
      await edit(p,{reasons:selected,rejectedReasons:selected.includes(reason)?(p.rejectedReasons||[]).filter(r=>r!==reason):[...new Set([...(p.rejectedReasons||[]),reason])]});b.setAttribute('aria-pressed',String(selected.includes(reason)));
      render();
    },'reason');b.setAttribute('aria-pressed',String(p.reasons.includes(reason)));reasons.append(b);
  }
  article.append(reasons);
  const notes=node('details','notes');notes.append(node('summary','',p.note?'Your note':'Add a reason in your own words'));
  const textarea=node('textarea');textarea.value=p.note;textarea.maxLength=10000;textarea.setAttribute('aria-label',`Note for post by ${p.author}`);
  const saved=node('span','note-status');
  notes.append(textarea,action('Save note',async()=>{await edit(p,{note:textarea.value});saved.textContent='Saved locally';notes.querySelector('summary').textContent=p.note?'Your note':'Add a reason in your own words';}),saved);article.append(notes);
  const foot=node('div','post-footer');
  foot.append(action(p.status==='kept'?'Back to review':'Keep',()=>decide(p,p.status==='kept'?'inbox':'kept')));
  foot.append(action(p.status==='dismissed'?'Restore':'Dismiss',async()=>{await decide(p,p.status==='dismissed'?'inbox':'dismissed');notice('Saved. Dismissed posts stay in your library and can be restored.');}));
  if(view==='inbox')foot.append(action('Later',async()=>{skipped.add(p.key);render();}));
  foot.append(link('Open on X ↗',p.url));article.append(foot);
  const meta=node('div','post-date',`Collected ${date(p.firstCollectedAt)} · @${p.owner}`);meta.style.marginTop='12px';article.append(meta);return article;
}
function stats(){
  $('#total').textContent=posts.length.toLocaleString();$('#all-count').textContent=posts.filter(p=>p.status!=='dismissed').length.toLocaleString();
  $('#kept-total').textContent=posts.filter(p=>p.status==='kept').length.toLocaleString();$('#review-total').textContent=posts.filter(p=>p.status==='inbox').length.toLocaleString();
}
function render(){
  const query=$('#search').value.toLowerCase().trim(),reason=$('#reason').value,owner=$('#owner').value;
  const terms=query.split(/\s+/).filter(Boolean),semantic=!!query&&$('#search-mode').value==='meaning';
  $('#sort').disabled=semantic||view==='inbox';
  let matches=posts.filter(p=>{
    if(view==='dismissed'?p.status!=='dismissed':p.status==='dismissed')return false;
    if(['likes','bookmarks'].includes(view)&&!p.sources.includes(view))return false;
    if(['inbox','kept'].includes(view)&&p.status!==view)return false;
    const categories=D.labels(p,discovery.get(p.key));
    if(reason==='uncategorized'?categories.length>0:reason&&!categories.includes(reason))return false;
    if(owner&&p.owner!==owner)return false;
    const text=[p.text,p.author,p.authorName,p.context,p.note,p.quotedPost?.text,...p.links,...p.reasons].join(' ').toLowerCase();
    return semantic||terms.every(t=>text.includes(t));
  });
  const sort=$('#sort').value;
  matches.sort((a,b)=>sort==='collected'?b.firstCollectedAt.localeCompare(a.firstCollectedAt):sort==='oldest'?(a.postedAt||'9999').localeCompare(b.postedAt||'9999'):(b.postedAt||'').localeCompare(a.postedAt||''));
  if(view==='inbox')matches=D.queue(matches,discovery,reason==='uncategorized'?'':reason,skipped);
  if(semantic){
    if(!queryVector)matches=[];
    else{const scored=matches.map(p=>{const vectors=discovery.get(p.key)?.vectors||[];const meaning=vectors.length?Math.max(...vectors.map(v=>D.cosine(v,queryVector))):0;return {p,meaning,lexical:D.lexical(p,query)};}).filter(r=>r.meaning>=.23||r.lexical===1).sort((a,b)=>(b.meaning+.16*b.lexical)-(a.meaning+.16*a.lexical));matches=scored.map(r=>r.p);notice(`Ranked by meaning and word matches. Category suggestions are estimates; your own labels take priority.`);}
  }
  const size=view==='inbox'?10:pageSize;
  page=Math.max(0,Math.min(page,Math.ceil(matches.length/size)-1));
  $('#view-title').textContent=labels[view];$('#result-count').textContent=`${matches.length.toLocaleString()} ${matches.length===1?'post':'posts'}`;
  $('#posts').replaceChildren(...matches.slice(page*size,(page+1)*size).map(card));
  if(!matches.length){
    const empty=node('div','empty');empty.append(node('h3','',semantic&&!queryVector?'Finding related posts…':posts.length?'Nothing in this view yet.':'Your next good find starts here.'));
    empty.append(node('p','',semantic&&!queryVector?'The first search loads a small model from this extension.':posts.length?'Try a different search or filter.':'Open your X History, click Start collecting, and scroll. Your saves will appear here.'));
    if(!posts.length)empty.append(link('Open bookmarks ↗','https://x.com/i/history'),link('Open likes ↗','https://x.com/i/history/likes'));
    $('#posts').append(empty);
  }
  $('#previous').disabled=page===0;$('#next').disabled=(page+1)*size>=matches.length;
  $('#page').textContent=matches.length?`Page ${page+1} of ${Math.ceil(matches.length/size)}`:'0 posts';
  $('#queue-help').hidden=view!=='inbox';
}
async function load(){
  posts=await getPosts();const selected=$('#owner').value;
  const byKey=new Map(posts.map(p=>[p.key,p]));
  for(const [key,r] of discovery){const p=byKey.get(key);if(!p||D.fingerprint(p)!==r.fingerprint)discovery.delete(key);}
  $('#owner').replaceChildren(new Option('All accounts',''),...[...new Set(posts.map(p=>p.owner))].sort().map(v=>new Option(`@${v}`,v)));
  $('#owner').value=selected;stats();indexStatus();render();
}
for(const r of GoldCore.reasons)$('#reason').append(new Option(r,r));
$('#reason').append(new Option('Uncategorized','uncategorized'));
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{view=b.dataset.view;page=0;document.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('selected',x===b));render();});
$('#search').oninput=search;
$('#search-mode').onchange=search;
for(const id of ['reason','owner','sort'])$(`#${id}`).onchange=()=>{page=0;render();};
$('#previous').onclick=()=>{page--;render();window.scrollTo(0,0);};$('#next').onclick=()=>{page++;render();window.scrollTo(0,0);};
$('#refresh').onclick=()=>load().catch(e=>notice(e.message,true));
$('#export').onclick=async()=>{
  try{
    const all=await getPosts();
    const data={format:'gold-collector',version:1,exportedAt:new Date().toISOString(),posts:all};
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=`gold-library-${new Date().toISOString().slice(0,10)}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);
    notice(`Exported ${all.length} posts, including dismissed posts and your notes.`);
  }catch(e){notice(e.message,true);}
};
$('#import').onchange=async event=>{
  const file=event.target.files[0];if(!file)return;
  try{
    if(file.size>100*1024*1024)throw new Error('Backup exceeds the 100 MB import limit.');
    const data=JSON.parse(await file.text());
    if(data.format!=='gold-collector'||data.version!==1||!Array.isArray(data.posts))throw new Error('Choose a Gold Collector v1 JSON backup.');
    const normalized=data.posts.map(p=>{
      const clean=GoldCore.normalize(p);if(!clean)throw new Error('Backup contains an invalid post; nothing was imported.');
      const iso=value=>typeof value==='string'&&Number.isFinite(Date.parse(value))?new Date(value).toISOString():clean.firstCollectedAt;
      return {...clean,firstCollectedAt:iso(p.firstCollectedAt),lastCollectedAt:iso(p.lastCollectedAt),note:typeof p.note==='string'?p.note.slice(0,10000):'',status:['inbox','kept','dismissed'].includes(p.status)?p.status:'inbox',reasons:Array.isArray(p.reasons)?p.reasons.filter(r=>GoldCore.reasons.includes(r)):[],rejectedReasons:Array.isArray(p.rejectedReasons)?p.rejectedReasons.filter(r=>GoldCore.reasons.includes(r)):[]};
    });
    const result=await savePosts(normalized);await load();notice(`Imported ${result.added} new posts. Existing notes and review decisions were preserved.`);
  }catch(e){notice(e.message,true);}finally{event.target.value='';}
};
// Explicit Refresh avoids replacing a draft note when the user switches tabs.
$('#prepare').onclick=prepare;
$('#stop-index').onclick=()=>{worker?.postMessage({type:'cancel'});indexJob++;indexing=false;$('#prepare').disabled=false;$('#stop-index').hidden=true;indexStatus();render();};
$('#undo').onclick=async()=>{if(lastUndo){await edit(lastUndo.p,{status:lastUndo.previous});lastUndo=null;$('#undo').hidden=true;render();}};
$('#reset-later').onclick=()=>{skipped.clear();render();};
(async()=>{
  for(const r of await readDiscovery())discovery.set(r.key,r);
  await load();
  const byKey=new Map(posts.map(p=>[p.key,p]));
  // Optional index prepared on this computer. Never contains review decisions.
  try{const response=await fetch('personal-index.json');if(response.ok){const seed=await response.json();if(seed.version===D.version){for(const r of seed.records)if(!discovery.has(r.key)&&byKey.has(r.key)&&D.fingerprint(byKey.get(r.key))===r.fingerprint)discovery.set(r.key,r);}}}catch{}
  indexStatus();render();
})().catch(e=>notice(`Could not open local storage: ${e.message}`,true));
