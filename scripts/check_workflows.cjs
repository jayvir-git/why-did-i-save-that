// Real browser + disposable HTTP workspace. No personal data, no provider usage.
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const path=require('node:path');
const os=require('node:os');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const child=spawn(process.env.PYTHON || 'python',['scripts/preview_ui.py','--port','8773'],{cwd:root,windowsHide:true});
let output='';child.stdout.on('data',d=>output+=d);child.stderr.on('data',d=>output+=d);
const wait=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 let browser;
 try{
  for(let i=0;i<100&&!output.includes('Disposable UI preview:');i++){if(child.exitCode!==null)throw Error(output);await wait(100);}
  assert.match(output,/Disposable UI preview:/);
  browser=await chromium.launch({channel:'msedge',headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const base='http://127.0.0.1:8773';
  await page.goto(base);await page.locator('#search-detail:not([hidden])').waitFor();
  await page.selectOption('#mode','keyword');await page.fill('#query','Targetpicker');await page.locator('#search-submit').click();
  await page.locator('#search-detail').filter({hasText:'1 of 1'}).waitFor();
  await page.getByRole('button',{name:'Read post',exact:true}).click();
  await page.locator('#reader').getByRole('button',{name:'Evidence coverage / Request review',exact:true}).click();
  await page.locator('#media-target option').nth(3).waitFor({state:'attached'});
  assert.equal(await page.inputValue('#media-target'),'');assert.equal(await page.locator('#queue-review').isDisabled(),true);
  await page.selectOption('#media-target','2');await page.locator('#target-preview').filter({hasText:'Captured attachment b'}).waitFor();
  let queued;
  await page.route('**/api',async route=>{const req=route.request().postDataJSON();if(req.operation==='queue_review')queued=req.args;await route.continue();});
  await page.fill('#media-objective','Inspect specifically attachment B');await page.locator('#queue-review').click();await page.locator('#media-dialog').waitFor({state:'hidden'});
  const api=(operation,args={})=>page.evaluate(async({operation,args})=>{const response=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation,args})});if(!response.ok)throw Error(await response.text());return response.json();},{operation,args});
  const source=(await api('get',{observation_ids:[queued.observation_id]}))[0];assert.equal(source.text,'Captured attachment b');
  await page.locator('[data-view="media"]').click();await page.getByRole('heading',{name:'Inspect specifically attachment B',exact:true}).waitFor();
  // Returned usage failure stays in the UI; no real Codex request is made.
  await page.route('**/api',async route=>{const req=route.request().postDataJSON();if(req.operation==='start_work')return route.fulfill({status:429,contentType:'application/json',body:JSON.stringify({error:'Codex usage limit reached'})});return route.fallback();});
  await page.getByRole('button',{name:'Start Codex review',exact:true}).click();await page.locator('#message').filter({hasText:'usage limit'}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Start Codex review',exact:true}).isEnabled(),true);
  await page.unrouteAll({behavior:'wait'});
  // Commit the note, then drop its HTTP acknowledgment. The UI reconciles receipt.
  let saves=0;
  await page.route('**/api',async route=>{const req=route.request().postDataJSON();if(req.operation==='save_note'){saves++;await route.fetch();return route.abort('failed');}return route.continue();});
  await page.locator('#new-note').click();await page.fill('#title','Lost acknowledgment fixture');await page.fill('#note','A draft that must save exactly once.');await page.locator('#save-note').click();await page.locator('#note-dialog').waitFor({state:'hidden'});
  assert.equal(saves,1);await page.unrouteAll({behavior:'wait'});
  const notes=await api('research_search',{text:'Lost acknowledgment fixture'});assert.equal(notes.receipt.count,1);
  await page.locator('[data-view="library"]').first().click();
  await page.locator('#reader').getByRole('button',{name:'Plan an action',exact:true}).click();await page.fill('#action-next','Try this approach');await page.fill('#action-reason','To build a prototype');await page.locator('#save-action').click();await page.locator('#action-dialog').waitFor({state:'hidden'});
  await page.locator('[data-view="actions"]').click();await page.getByRole('heading',{name:'Try this approach',exact:true}).waitFor();
  await page.getByRole('button',{name:'Update action / record outcome',exact:true}).click();await page.selectOption('#action-state','done');await page.fill('#action-outcome','A working prototype with source evidence');await page.locator('#save-action').click();await page.locator('#action-dialog').waitFor({state:'hidden'});await page.locator('#results').filter({hasText:'A working prototype'}).waitFor();
  await page.locator('[data-view="library"]').first().click();
  // Polling notices external evidence without replacing the selected reader.
  await page.evaluate(()=>refreshStatus());
  const chosen=await page.locator('#reader-content').textContent();
  const oid=await page.evaluate(()=>selectedCard._row.observation_id);
  const req=await api('queue_review',{client_request_id:'browser-external-queue',observation_id:oid,objective:'External change'});
  await api('save_review',{client_request_id:'browser-external-complete',request_id:req.id,description:'Fresh external evidence',kind:'transcript'});
  await page.evaluate(()=>refreshStatus());assert.equal(await page.locator('#reader-content').textContent(),chosen);
  await page.locator('#updates:not([hidden])').waitFor();await page.locator('#accept-updates').click();await page.locator('#reader:not([hidden])').waitFor();
  assert.equal(await page.evaluate(()=>selectedCard._row.observation_id),oid);
  await page.locator('#close-reader').click();await page.getByRole('button',{name:'Read post',exact:true}).focus();await page.keyboard.press('Enter');await page.locator('#close-reader').waitFor();assert.equal(await page.locator('#close-reader').evaluate(n=>n===document.activeElement),true);
  await page.locator('#close-reader').click();assert.equal(await page.getByRole('button',{name:'Read post',exact:true}).evaluate(n=>n===document.activeElement),true);
  await page.screenshot({path:path.join(os.tmpdir(),'inator-workflows-desktop.png'),fullPage:true});
  await page.setViewportSize({width:320,height:800});
  for(const view of ['library','research','media','actions']){await page.locator(`[data-view="${view}"]`).first().click();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`320px overflow: ${view}`);}
  await page.screenshot({path:path.join(os.tmpdir(),'inator-workflows-mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('Browser workflows passed: explicit target, visible usage error, lost-response reconciliation, actions/outcomes, external updates, focus return, 320px views.');
 }finally{if(browser)await browser.close();child.kill();}
})().catch(e=>{console.error(e);console.error(output);process.exitCode=1;});
