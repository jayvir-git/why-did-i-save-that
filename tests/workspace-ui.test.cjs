const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

// A small DOM adapter lets navigation run through the real app controller.
// The API records requests; no search engine or personal collection is involved.
function harness(initialHash = '') {
  class Element {
    constructor(tag = 'div') { this.tagName = tag.toUpperCase(); this.children = []; this.dataset = {}; this.attrs = {}; this.value = ''; this.textContent = ''; this.hidden = false; this.disabled = false; this.classList = { add() {}, remove() {}, toggle() {} }; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children = [...nodes]; }
    setAttribute(key, value) { this.attrs[key] = value; }
    getAttribute(key) { return this.attrs[key]; }
    removeAttribute(key) { delete this.attrs[key]; }
    addEventListener() {}
    focus() {}
    select() {}
  }
  const nodes = new Map();
  const get = key => { if (!nodes.has(key)) nodes.set(key, new Element()); return nodes.get(key); };
  const nav = ['library', 'research', 'media'].map(view => { const n = new Element('button'); n.dataset.view = view; return n; });
  const calls = [];
  let release;
  const context = vm.createContext({
    document: { querySelector: get, querySelectorAll: selector => selector === '[data-view]' ? nav : [], createElement: tag => new Element(tag), addEventListener() {} },
    sessionStorage: { getItem() { return null; }, setItem() {} },
    window: { scrollY: 0, scrollTo() {}, location:{hash:initialHash}, events:{}, addEventListener(name, fn) { this.events[name] = fn; }, history:{pushState(_state, _title, hash) { context.window.location.hash = hash; }} }, URL, console,
    fetch: async (_url, init) => {
      const request = JSON.parse(init.body); calls.push(request);
      if (request.operation === 'search_library' && context.delaySearch) await new Promise(resolve => { release = resolve; });
      const data = request.operation === 'inventory' ? { posts: 1, sources: { likes: 1, bookmarks: 0 } }
        : request.operation === 'result' ? { rows: [{ author: 'tester', text: 'A useful website', url: 'https://example.com', supporting_passages: [] }], next_offset: context.nextOffset ?? null }
        : { receipt: { result_id: request.operation + calls.length, count: context.totalCount || 1 } };
      return { ok: true, json: async () => data };
    }
  });
  get('#mode').value = 'keyword';
  vm.runInContext(fs.readFileSync('gold_workspace/web/app.js', 'utf8'), context);
  const run = code => vm.runInContext(code, context);
  const settle = () => new Promise(resolve => setImmediate(resolve));
  return { context, get, calls, run, settle, release: () => release() };
}

test('returning to Library restores results without searching again', async () => {
  const h = harness();
  h.get('#query').value = 'website';
  await h.run('load()');
  const initial = h.get('#results').children[0].children[0];
  await h.run("switchView('research')"); await h.settle();
  await h.run("switchView('library')"); await h.settle();
  assert.equal(h.calls.filter(c => c.operation === 'search_library').length, 1, 'tab navigation must not repeat a library search');
  assert.equal(h.calls.filter(c => c.operation === 'result' && c.args.result_id.startsWith('search_library')).length, 1, 'tab navigation must not fetch the same result page again');
  assert.equal(h.get('#results').children[0].children[0], initial, 'restore the existing results rather than rebuilding them');
});

test('clicking the active Library tab does not start another request', async () => {
  const h = harness(); h.get('#query').value = 'website'; await h.run('load()');
  h.run("switchView('library')"); await h.settle();
  assert.equal(h.calls.filter(c => c.operation === 'search_library').length, 1);
});

test('an unfinished search completes in its own view without being repeated', async () => {
  const h = harness(); h.context.delaySearch = true; h.get('#query').value = 'website';
  const pending = h.run('load()');
  h.run("switchView('research')"); await h.settle();
  h.release(); await pending;
  assert.equal(h.run("viewStates.library.loaded"), true);
  h.run("switchView('library')"); await h.settle();
  assert.equal(h.calls.filter(c => c.operation === 'search_library').length, 1);
  assert.equal(h.get('#results').children[0].children.length, 1);
  assert.equal(h.get('#search-submit').disabled, false);
});

test('unsubmitted query edits survive navigation without triggering a search', async () => {
  const h = harness(); h.get('#query').value = 'website'; await h.run('load()');
  h.get('#query').value = 'different idea';
  h.run("switchView('media')"); await h.settle(); h.run("switchView('library')"); await h.settle();
  assert.equal(h.get('#query').value, 'different idea');
  assert.equal(h.run('viewStates.library.searched'), 'website');
  assert.equal(h.calls.filter(c => c.operation === 'search_library').length, 1);
});

test('explicit refresh performs a new search', async () => {
  const h = harness(); h.get('#query').value = 'website'; await h.run('load()');
  h.get('#refresh-results').onclick(); await h.settle();
  assert.equal(h.calls.filter(c => c.operation === 'search_library').length, 2);
});

test('Research is reused until a save marks it dirty', async () => {
  const h = harness(); h.run("switchView('research')"); await h.settle();
  h.run("switchView('library')"); h.run("switchView('research')"); await h.settle();
  assert.equal(h.calls.filter(c => c.operation === 'research_search').length, 1);
  h.run("viewStates.research.dirty = true; switchView('library'); switchView('research')"); await h.settle();
  assert.equal(h.calls.filter(c => c.operation === 'research_search').length, 2);
});

test('a late search response cannot overwrite a newer search', async () => {
  const h = harness(); h.context.delaySearch = true; h.get('#query').value = 'old idea';
  const old = h.run('load()');
  h.context.delaySearch = false; h.get('#query').value = 'new idea'; await h.run('load()');
  const currentResult = h.run('viewStates.library.resultId');
  const currentCard = h.get('#results').children[0].children[0];
  h.release(); await old;
  assert.equal(h.run('viewStates.library.resultId'), currentResult);
  assert.equal(h.get('#results').children[0].children[0], currentCard);
  assert.equal(h.run('viewStates.library.searched'), 'new idea');
});

test('changing Scan/Read keeps result nodes and makes no API requests', async () => {
  const h = harness(); h.get('#query').value = 'website'; await h.run('load()');
  const card = h.get('#results').children[0].children[0];
  const count = h.calls.length;
  h.get('#read-view').onclick(); h.get('#scan-view').onclick();
  assert.equal(h.calls.length, count);
  assert.equal(h.get('#results').children[0].children[0], card);
  assert.equal(h.get('#scan-view').getAttribute('aria-pressed'), 'true');
  assert.equal(h.get('#read-view').getAttribute('aria-pressed'), 'false');
});

test('result ordinals and loaded count continue across pagination', async () => {
  const h = harness(); h.context.nextOffset = 1; h.context.totalCount = 2;
  h.get('#query').value = 'website'; await h.run('load()');
  h.context.nextOffset = null;
  await h.get('#more').onclick();
  const cards = h.get('#results').children[0].children;
  assert.equal(cards[0].children[0].children[0].textContent, '01');
  assert.equal(cards[1].children[0].children[0].textContent, '02');
  assert.match(h.get('#search-detail').textContent, /^2 of 2 loaded/);
});

test('thumbnail OCR remains explicitly distinguished from image text', () => {
  const h = harness();
  assert.equal(h.run("passageLabel({coverage:'video_thumbnail_ocr'})"), 'Video thumbnail text only');
  assert.equal(h.run("passageLabel({coverage:'image_ocr'})"), 'Image text · OCR');
});

test('Library opens with a browse request and reuses it across tabs', async () => {
  const h = harness(); await h.settle();
  const requests = h.calls.filter(c => c.operation === 'search_library');
  assert.equal(requests.length, 1);
  assert.equal(requests[0].args.text, '');
  assert.equal(h.run('viewStates.library.effectiveMode'), 'browse');
  h.run("switchView('research')"); await h.settle();
  h.run("switchView('library')"); await h.settle();
  assert.equal(h.calls.filter(c => c.operation === 'search_library').length, 1);
});

test('reader preserves list nodes and selection across navigation without fetching', async () => {
  const h = harness(); await h.settle();
  const card = h.get('#results').children[0].children[0];
  const requests = h.calls.length;
  h.run("openReader({text:'Complete source text',supporting_passages:[]}, viewStates.library.content.children[0], 1, el('button'))");
  assert.equal(h.get('#reader').hidden, false);
  assert.equal(h.calls.length, requests);
  h.run("switchView('research')"); await h.settle();
  assert.equal(h.get('#reader').hidden, true);
  h.run("switchView('library')");
  assert.equal(h.get('#reader').hidden, false);
  h.get('#close-reader').onclick();
  assert.equal(h.get('#reader').hidden, true);
  assert.equal(h.get('#results').children[0].children[0], card);
});

test('Browse all clears the query and invalidates the old reading pane', async () => {
  const h = harness(); h.get('#query').value = 'website'; await h.run('load()');
  h.run("openReader({text:'Source',supporting_passages:[]}, viewStates.library.content.children[0], 1, el('button'))");
  h.get('#browse-all').onclick(); await h.settle();
  assert.equal(h.get('#query').value, '');
  assert.equal(h.run('viewStates.library.searched'), '');
  assert.equal(h.get('#reader').hidden, true);
});


test('destination links and browser Back restore cached source selection', async () => {
  const h = harness(); await h.settle();
  h.run("openReader({text:'Source',supporting_passages:[]}, viewStates.library.content.children[0], 1, el('button'))");
  h.run("document.querySelectorAll('[data-view]')[1].onclick({preventDefault(){}})"); await h.settle();
  assert.equal(h.context.window.location.hash, '#notes');
  assert.equal(h.run('view'), 'research');
  const count = h.calls.length;
  h.context.window.location.hash = '#sources';
  h.context.window.events.popstate(); await h.settle();
  assert.equal(h.run('view'), 'library');
  assert.equal(h.get('#reader').hidden, false);
  assert.equal(h.calls.length, count);
});

test('a direct Notes link opens Notes on initial load', async () => {
  const h = harness('#notes'); await h.settle();
  assert.equal(h.run('view'), 'research');
  assert.equal(h.get('#page-title').textContent, 'Notes');
  assert.equal(h.calls.filter(c => c.operation === 'research_search').length, 1);
});
