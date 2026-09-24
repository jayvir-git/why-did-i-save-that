// Optional browser acceptance for the generated, offline visual specification.
// Requires Playwright; uses no personal workspace data and makes no app API calls.
const assert = require('node:assert/strict');
const path = require('node:path');
const os = require('node:os');
const {pathToFileURL} = require('node:url');
const {chromium} = require('playwright');

(async () => {
  const browser = await chromium.launch({headless:true, channel:'msedge'});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[]; page.on('pageerror',e=>errors.push(e.message));
    await page.goto(pathToFileURL(path.resolve(__dirname,'../docs/visual-spec.html')).href);
    await page.getByRole('heading',{name:'Review queue and tracked execution',exact:true}).waitFor();
    const diagrams=await page.locator('nav button').evaluateAll(nodes=>nodes.slice(0,8).map(n=>n.dataset.section));
    for (const id of diagrams) {
      await page.locator(`nav button[data-section="${id}"]`).click();
      const nodes=page.locator('.node');
      for (let i=0;i<await nodes.count();i++) {
        await nodes.nth(i).click();
        assert.equal(await nodes.nth(i).getAttribute('aria-pressed'),'true');
        assert.ok(await page.locator('.detail h3').textContent());
        assert.ok(await page.locator('.transitions .transition').count());
      }
    }
    await page.locator('nav button[data-section="decisions"]').click();
    await page.getByRole('searchbox',{name:'Search decisions'}).fill('D38');
    assert.equal(await page.locator('article.rule').count(),1);
    await page.locator('nav button[data-section="scenarios"]').click();
    await page.getByRole('button',{name:'Next',exact:true}).click();
    assert.equal(await page.locator('.step.active .number').textContent(),'2');
    await page.locator('.scenario-menu button').nth(1).click();
    assert.equal(await page.locator('.step.active .number').textContent(),'1');
    await page.locator('nav button[data-section="catalog"]').click();
    await page.getByRole('combobox',{name:'API surface'}).selectOption('web');
    const data=require('../docs/visual-spec.json');
    assert.equal(await page.locator('article.op').count(),data.operations.filter(o=>o.web).length);
    await page.locator('nav button[data-section="improvements"]').click();
    assert.equal(await page.locator('.proposal-row').count(),data.gaps.length);
    await page.locator('nav button[data-section="coverage"]').click();
    await page.locator('nav button[data-section="reviews"]').click();
    await page.locator('[data-node="pending"]').click();
    await page.screenshot({path:path.join(os.tmpdir(),'inator-visual-spec-desktop.png'),fullPage:true});
    await page.setViewportSize({width:360,height:800});
    for (const id of [...diagrams,'decisions','scenarios','improvements','catalog','coverage']) {
      await page.locator(`nav button[data-section="${id}"]`).click();
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Page overflow in ${id}`);
    }
    await page.locator('nav button[data-section="reviews"]').click();
    await page.screenshot({path:path.join(os.tmpdir(),'inator-visual-spec-mobile.png'),fullPage:true});
    assert.deepEqual(errors,[]);
    console.log('Visual specification: all maps/nodes, filters, scenario steps, API boundary and 360px layout passed; no browser errors.');
    console.log('Screenshots: '+path.join(os.tmpdir(),'inator-visual-spec-desktop.png')+' and '+path.join(os.tmpdir(),'inator-visual-spec-mobile.png'));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
