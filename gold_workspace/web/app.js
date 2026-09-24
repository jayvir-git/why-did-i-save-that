'use strict';

const $ = selector => document.querySelector(selector);
const el = (tag, text, cls) => {
  const node = document.createElement(tag);
  if (text != null) node.textContent = text;
  if (cls) node.className = cls;
  return node;
};
let view = 'library';
// Keep each view's DOM and request lifecycle separate. Navigation is not a search.
const viewStates = Object.fromEntries(['library', 'research', 'media', 'actions'].map(key => [key, {
  key, content: el('div', null, 'result-list'), resultId: null, next: null,
  generation: 0, busy: false, paging: false, loaded: false, dirty: false,
  searched: '', mode: 'hybrid', status: '', tone: '', scroll: 0,
  total: null, loadedCount: 0, completedAt: null, elapsed: null, effectiveMode: null
}]));
$('#results').append(viewStates.library.content);
let density = 'scan';
try { if (localStorage.getItem('gold-result-layout') === 'read') density = 'read'; } catch { /* Storage is optional. */ }
function setDensity(value) {
  density = value === 'read' ? 'read' : 'scan';
  $('#results').classList.toggle('scan-view', density === 'scan');
  $('#scan-view').setAttribute('aria-pressed', String(density === 'scan'));
  $('#read-view').setAttribute('aria-pressed', String(density === 'read'));
  try { localStorage.setItem('gold-result-layout', density); } catch { /* Keep this session usable. */ }
}
$('#scan-view').onclick = () => setDensity('scan');
$('#read-view').onclick = () => setDensity('read');
setDensity(density);

let evidence = [], mediaSource = null, pendingInvestigation = null;
const queries = { library: '', research: '', media: '', actions: '' };
const views = {
  library: ['Sources', 'YOUR LOCAL ARCHIVE', 'Sources', 'Browse your sources. Keep what matters.'],
  research: ['Notes', 'MAKE SOMETHING OF IT', 'Notes', 'Your notes, findings, and the sources that brought you here.'],
  actions: ['Actions', 'PUT IT TO USE', 'Actions', 'Why you saved it, what comes next, and what happened.'],
  media: ['Review queue', 'LOOK A LITTLE CLOSER', 'Review queue', 'Questions about images and videos, ready for a closer look.']
};
function requestError(data, status) {
  const detail = typeof data?.error === 'string' ? data.error : data?.error?.message || data?.message || '';
  const code = data?.error?.code || data?.code || '';
  if (/usage.?limit|quota|insufficient_quota|usage_limit|out of.*(usage|credits)/i.test(`${code} ${detail}`)) {
    return 'Agent usage limit reached. Check your agent account and wait for its usage to reset or add available usage, then retry. Your saved collection is still available.';
  }
  if (status === 429) return 'Too many requests. Wait a moment, then try again.';
  return detail || 'The request could not be completed. Please try again.';
}
async function api(operation, args = {}) {
  const controller = new AbortController();
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => {
      reject(Error('The request timed out. Check that the local app is running, then retry. If you were saving, refresh first to check whether it completed.'));
      controller.abort();
    }, 30000);
  });
  try {
    return await Promise.race([timeout, (async () => {
      let response;
      try {
        response = await fetch('/api', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ operation, args }), signal: controller.signal });
      } catch (error) {
        if (error.name === 'AbortError') throw error;
        throw Error('Couldn’t reach your workspace. Check that the local app is running, then retry.');
      }
      let data;
      try { data = await response.json(); }
      catch { throw Error('The workspace returned an unreadable response. Reload the app and try again.'); }
      if (!response.ok || data?.error) { const error = Error(requestError(data, response.status)); error.confirmed = response.status === 400; throw error; }
      return data;
    })()]);
  } finally { clearTimeout(timer); }
}
function message(text, tone = '', state = viewStates[view]) {
  state.status = text; state.tone = tone;
  if (state.key !== view) return;
  $('#message').textContent = text;
  $('#message').hidden = !text;
  $('#message').dataset.tone = tone;
  $('#message').setAttribute('role', tone === 'error' ? 'alert' : 'status');
}
function action(parent, label, fn, cls) {
  const button = el('button', label, cls);
  button.type = 'button';
  button.onclick = async () => {
    const originalLabel = button.textContent;
    try {
      const result = fn();
      if (result && typeof result.then === 'function') { button.disabled = true; button.textContent = 'Working…'; await result; }
    } catch (error) { message(error.message, 'error'); }
    finally { button.disabled = false; if (button.textContent === 'Working…') button.textContent = originalLabel; }
  };
  parent.append(button);
  return button;
}
function sourceLink(parent, url, label = 'Open source ↗') {
  try {
    const parsed = new URL(url);
    if (!['http:', 'https:'].includes(parsed.protocol)) return;
    const link = el('a', label); link.href = parsed.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; parent.append(link);
  } catch { /* Missing or invalid source URLs are not links. */ }
}
function disclosure(parent, title, cls = 'evidence-details') {
  const details = el('details', null, cls); details.append(el('summary', title)); parent.append(details); return details;
}
function passageLabel(passage) {
  const coverage = passage.coverage || passage.role || '';
  // A thumbnail OCR result must never be presented as analysis of the video.
  return coverage.includes('thumbnail') ? 'Video thumbnail text only' : coverage.includes('ocr') ? 'Image text · OCR' : coverage.includes('transcript') ? 'Imported transcript' : /interpretation|visual/.test(coverage) ? 'Interpretation' : coverage === 'html_text_only' ? 'Linked page' : /pdf/i.test(coverage) ? 'PDF text' : coverage.includes('quote') ? 'Quoted post' : coverage === 'post' ? 'Post text' : 'Source excerpt';
}
function saveDraft() {
  $('#new-note').textContent = $('#title').value || $('#note').value || evidence.length ? 'Continue note' : '+ New note';
  try { sessionStorage.setItem('gold-note-draft', JSON.stringify({ title: $('#title').value, note: $('#note').value, evidence, pendingInvestigation })); } catch { /* The editor still works if browser storage is unavailable. */ }
}
function updateCitations() {
  $('#citation').textContent = evidence.length ? `${evidence.length} source excerpt${evidence.length === 1 ? '' : 's'} attached` : 'No sources attached yet. Use “Add to note” on a result.';
  $('#citation-list').replaceChildren();
  evidence.forEach((item, index) => {
    const li = el('li', item.quote.length > 130 ? item.quote.slice(0, 130) + '…' : item.quote);
    action(li, 'Remove', () => { evidence.splice(index, 1); updateCitations(); saveDraft(); }).setAttribute('aria-label', `Remove source excerpt ${index + 1}`);
    $('#citation-list').append(li);
  });
}
function openNote() {
  $('#note-status').textContent = '';
  $('#note-dialog').showModal();
  ($('#title').value ? $('#note') : $('#title')).focus();
}
function addToNote(row) {
  const spans = row.supporting_passages || [];
  for (const p of spans) {
    const item = { observation_id: p.observation_id, field: p.field || 'text', start: p.start, end: p.end, quote: p.quote };
    if (!evidence.some(e => e.observation_id === item.observation_id && e.field === item.field && e.start === item.start && e.end === item.end)) evidence.push(item);
  }
  updateCitations(); saveDraft(); openNote();
}
function renderLibrary(row, card, number, reading = false) {
  card.classList.add('library-result'); card._row = row; card._number = number;
  const heading = el('div', null, 'card-heading');
  const rank = el('span', String(number).padStart(2, '0'), 'result-number'); rank.setAttribute('aria-label', `Result ${number}`); heading.append(rank);
  let domain = 'Saved source';
  try { domain = new URL(row.url).hostname.replace(/^www\./, ''); } catch { /* No source URL. */ }
  const byline = el('div', null, 'result-byline'); byline.append(el('h3', row.author ? '@' + row.author.replace(/^@/, '') : 'Saved post'), el('p', domain, 'meta'));
  heading.append(byline); sourceLink(heading, row.url); card.append(heading);
  const text = row.text || 'This save has an attachment, but no captured post text.';
  if (text.length <= 600) card.classList.add('short-post');
  const body = el('p', reading ? text : text.slice(0, 600) + (text.length > 600 ? '…' : ''), 'post-text'); card.append(body);
  const unique = [...new Map((row.supporting_passages || []).map(p => [p.quote, p])).values()];
  if (unique.length) {
    card.classList.add('has-match');
    const passage = unique[0];
    const preview = el('div', null, 'match-preview');
    if (passage.role === 'post') preview.classList.add('post-match');
    const quote = passage.quote || '';
    preview.append(el('p', (row.browsing ? 'SOURCE · ' : 'MATCH · ') + passageLabel(passage), 'passage-label'), el('blockquote', quote.length > 360 ? quote.slice(0, 360) + '…' : quote));
    card.append(preview);
    const details = disclosure(card, `Evidence (${unique.length} excerpt${unique.length === 1 ? '' : 's'})`);
    for (const source of unique) details.append(el('p', passageLabel(source), 'passage-label'), el('blockquote', source.quote));
  }
  const actions = el('div', null, 'actions');
  if (!reading) {
    const toggle = action(actions, 'Read post', () => {
      openReader(row, card, number, toggle);
    }, 'post-toggle'); card._readTrigger = toggle; toggle.setAttribute('aria-expanded', 'false');
  }
  const cite = action(actions, '+ Add to note', () => addToNote(row), 'cite-action');
  if (!unique.length) { cite.disabled = true; cite.title = 'No exact source excerpts available for this result.'; }
  action(actions, 'Evidence coverage / Request review', () => openMediaPicker(row));
  action(actions, 'Plan an action', () => openAction(row));
  card.append(actions);
  if (row.postedAt) {
    const date = new Date(row.postedAt);
    if (!Number.isNaN(date.getTime())) byline.append(el('p', date.toLocaleDateString([], {year:'numeric',month:'short',day:'numeric'}), 'meta'));
  }
  if (!row.postedAt) byline.append(el('p', 'Date unavailable', 'meta'));
  if (reading) {
    card.classList.add('reader-article');
    card.append(el('p', unique.length ? [...new Set(unique.map(passageLabel))].join(' · ') : 'No extracted evidence available.', 'coverage-note'));
  }
}
let selectedCard = null, readerTrigger = null, readerScroll = 0;
function closeReader(restoreFocus = true) {
  $('#reader').hidden = true;
  $('#library-workbench').classList.remove('reader-open');
  if (selectedCard) selectedCard.classList.remove('selected-source');
  if (readerTrigger) readerTrigger.setAttribute('aria-expanded', 'false');
  if (restoreFocus && readerTrigger) { readerTrigger.focus(); window.scrollTo({top:readerScroll,behavior:'instant'}); }
  selectedCard = null;
}
function openReader(row, card, number, trigger) {
  if (selectedCard) selectedCard.classList.remove('selected-source');
  if (readerTrigger) readerTrigger.setAttribute('aria-expanded', 'false');
  selectedCard = card; readerTrigger = trigger; readerScroll = window.scrollY;
  trigger.setAttribute('aria-expanded', 'true');
  card.classList.add('selected-source');
  const article = el('article', null, 'source-card');
  renderLibrary(row, article, number, true);
  $('#reader-content').replaceChildren(article);
  $('#reader').hidden = false;
  $('#library-workbench').classList.add('reader-open');
  $('#reader').scrollTop = 0;
  $('#close-reader').focus();
}
$('#close-reader').onclick = () => closeReader();
$('#browse-all').onclick = () => { $('#query').value = ''; load(); };
function renderResearch(row, card) {
  card.append(el('h3', row.name), el('p', `${row.kind} · Version ${row.version}`, 'state-tag'));
  if (row.changed_evidence?.length) card.append(el('p', 'Worth another look: a cited source has a newer captured version.', 'review-warning'));
  else if (row.newer_corpus_available) card.append(el('p', 'New material has arrived in your library since this note.', 'meta'));
  const content = row.content;
  const summary = typeof content === 'string' ? content : content?.statement || content?.text || content?.conclusion || content?.summary;
  card.append(el('p', typeof summary === 'string' ? summary : 'Open the saved details to explore this finding.', 'research-text'));
  if (content?.evidence?.length) {
    const sources = disclosure(card, `${content.evidence.length} cited source excerpt${content.evidence.length === 1 ? '' : 's'} · ${content.status || 'unverified'}`);
    for (const citation of content.evidence) sources.append(el('blockquote', citation.quote || 'Source reference saved without an excerpt.'));
  }
  const details = disclosure(card, 'Saved details'); details.append(el('pre', JSON.stringify(content, null, 2)));
}
function renderMedia(row, card) {
  card._reviewId = row.id;
  card.append(el('h3', row.objective), el('p', row.state === 'pending' ? 'Awaiting review' : row.state === 'completed' ? 'Reviewed' : row.state, 'state-tag'));
  if (row.state === 'completed' && row.result) {
    const review = el('div'); review.hidden = true; card.append(review);
    let loaded = false;
    const read = action(card, 'Read review', async () => {
      if (!loaded) {
        const result = typeof row.result === 'string' ? JSON.parse(row.result) : row.result;
        const [saved] = await api('get', { observation_ids: [result.observation_id] });
        review.append(el('p', saved.text || saved.raw.text || 'No review text available.', 'research-text'));
        loaded = true;
      }
      review.hidden = !review.hidden; read.textContent = review.hidden ? 'Read review' : 'Hide review';
      read.setAttribute('aria-expanded', String(!review.hidden));
    }, 'text-button');
    read.setAttribute('aria-expanded', 'false');
  }
  const sourcePanel = el('div'); sourcePanel.hidden = true; card.append(sourcePanel);
  let inspected = false;
  const inspect = action(card, 'Inspect source', async () => {
    if (!inspected) {
      const [source] = await api('get', { observation_ids: [row.observation_id] });
      if (['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(source.raw.mime)) { const image = el('img'); image.src = '/media/' + row.observation_id; image.alt = 'Cached source image for this review'; sourcePanel.append(image); }
      if (source.raw.text) sourcePanel.append(el('p', source.raw.text, 'post-text'));
      sourceLink(sourcePanel, source.raw.url);
      disclosure(sourcePanel, 'Source details').append(el('pre', JSON.stringify(source.raw, null, 2)));
      inspected = true;
    }
    sourcePanel.hidden = !sourcePanel.hidden;
    inspect.textContent = sourcePanel.hidden ? 'Inspect source' : 'Hide source';
    inspect.setAttribute('aria-expanded', String(!sourcePanel.hidden));
  }, 'text-button');
  inspect.setAttribute('aria-expanded', 'false');
  if (row.state !== 'pending') return;
  card.append(el('p', 'Waiting for a person or agent. Start a tracked agent review below, or add your own analysis. Runs started here show progress and usage failures in Activity. Work started elsewhere is not tracked.', 'form-status'));
  const runState = el('p', '', 'review-warning'); runState.setAttribute('role', 'status'); card.append(runState);
  const providerLabel = el('label', 'Review provider'), provider = el('select');
  provider.id = 'provider-' + row.id; providerLabel.htmlFor = provider.id;
  for (const [value, text] of [['codex', 'Codex'], ['claude', 'Claude Code']]) { const option = el('option', text); option.value = value; provider.append(option); }
  provider.value = row.latest_run?.provider || 'codex';
  card.append(providerLabel, provider);
  card.append(el('p', 'Starting a review sends this selected source and question to the chosen provider using its CLI credentials and account allowance. A draft requires your review before it becomes evidence.', 'meta'));
  const start = action(card, 'Start ' + providerName(provider.value) + ' review', () => beginWork('review', row.id, provider.value), 'secondary');
  provider.onchange = () => { start.textContent = 'Start ' + providerName(provider.value) + ' review'; };
  const form = el('form', null, 'analysis-form');
  const label = el('label', 'Your analysis or transcript');
  const area = el('textarea'); area.rows = 4; area.required = true; area.id = 'analysis-' + row.id; label.htmlFor = area.id; area.placeholder = 'Describe what you inspected. Include timecodes for a transcript.';
  const typeLabel = el('label', 'Review type'); const kind = el('select'); kind.id = 'kind-' + row.id; typeLabel.htmlFor = kind.id;
  for (const [value, text] of [['visual', 'Visual analysis'], ['transcript', 'Transcript']]) { const option = el('option', text); option.value = value; kind.append(option); }
  const status = el('p', '', 'form-status'); status.setAttribute('role', 'status');
  const save = el('button', 'Save review', 'primary');
  form.append(label, area, typeLabel, kind, status, save);
  form.onsubmit = async event => {
    event.preventDefault(); if (!area.value.trim()) { status.textContent = 'Add an analysis or transcript first.'; return; }
    save.disabled = true; area.readOnly = true; kind.disabled = true; status.textContent = 'Saving review…';
    try { await durableWrite('review-'+row.id, 'save_review', { request_id: row.id, description: area.value.trim(), kind: kind.value, expected_version: row.version }); viewStates.media.dirty = true; await load('media'); message('Review saved. It’s now available in word search.', '', viewStates.media); }
    catch (error) { status.textContent = error.message; }
    finally { save.disabled = false; area.readOnly = false; kind.disabled = false; }
  };
  reviewRunViews.set(row.id, {node:runState, fallback:row.latest_run, card, area, status});
  syncReviewRunViews();
  card.append(form);
}
function render(rows, state = viewStates[view]) {
  for (const [index, row] of rows.entries()) {
    const card = el('article', null, 'source-card');
    ({ library: renderLibrary, research: renderResearch, media: renderMedia, actions: renderAction })[state.key](row, card, state.loadedCount + index + 1);
    state.content.append(card);
  }
}
function emptyState(state) {
  const view = state.key;
  const section = el('div', null, 'empty-state');
  const searched = state.searched;
  if (view === 'library' && !searched) return;
  const title = view === 'actions' ? 'Give a save a next step.' : view === 'media' ? 'Nothing waiting for a closer look.' : view === 'research' && !searched ? 'Your next finding belongs here.' : 'No matches this time.';
  const text = view === 'actions' ? 'Open a source and choose Plan an action to connect it to something you want to do.' : view === 'media' ? 'Request a media review from any source. Your questions will appear here.' : view === 'research' && !searched ? 'Write a note, or start in Sources and add a source to it.' : 'Try fewer words, a different phrase, or a broader idea.';
  section.append(el('h2', title), el('p', text));
  if (view === 'research' && !searched) action(section, '+ Write your first note', openNote, 'primary');
  else if (view === 'media' || view === 'actions') action(section, 'Explore Sources', () => switchView('library'), 'secondary');
  else action(section, 'Try another search', () => { $('#query').focus(); $('#query').select(); }, 'secondary');
  state.content.append(section);
}
function syncView(state = viewStates[view]) {
  if (state.key !== view) return;
  $('#results').setAttribute('aria-busy', String(state.busy || state.paging));
  $('#search-submit').disabled = state.busy;
  $('#more').hidden = state.next == null || state.busy;
  $('#more').disabled = state.paging;
  $('#refresh-results').hidden = !state.loaded && !state.busy;
  $('#refresh-results').disabled = state.busy || state.paging;
  $('#welcome').hidden = view !== 'library' || state.total !== 0 || !!state.searched || state.busy;
  $('#main').classList.toggle('showing-results', $('#welcome').hidden);
  $('#main').classList.toggle('library-view', view === 'library');
  $('#browse-all').hidden = view !== 'library' || !state.searched;
  $('#reader').hidden = view !== 'library' || !selectedCard;
  $('#library-workbench').classList.toggle('reader-open', view === 'library' && !!selectedCard);
  $('#density-controls').hidden = state.key !== 'library' || !state.loadedCount;
  $('#search-detail').hidden = !state.completedAt || state.busy || state.tone === 'error';
  if (state.completedAt) {
    const mode = state.key === 'library' ? ({ browse: 'Newest posted first · Undated last', keyword: 'Words only', hybrid: 'Words + meaning', semantic: 'Meaning only' })[state.effectiveMode] : state.key === 'research' ? 'Saved notes' : state.key === 'actions' ? 'Source actions' : 'Media reviews';
    const time = new Date(state.completedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    $('#search-detail').textContent = `${state.loadedCount.toLocaleString()} of ${state.total.toLocaleString()} loaded · ${mode} · Retrieved ${time} in ${(state.elapsed / 1000).toFixed(1)}s`;
  }
  message(state.status, state.tone, state);
}
async function page(append = false, state = viewStates[view], ticket = state.generation) {
  const current = state.resultId;
  const data = await api('result', { result_id: current, offset: append ? state.next : 0, limit: 20 });
  if (ticket !== state.generation || current !== state.resultId) return;
  if (!append) { state.content.replaceChildren(); state.loadedCount = 0; if (state.key === 'media') reviewRunViews.clear(); }
  render(data.rows, state); state.loadedCount += data.rows.length; state.next = data.next_offset;
  if (!append && !data.rows.length) emptyState(state);
  syncView(state);
}
async function load(targetView = view) {
  const state = viewStates[targetView];
  const ticket = ++state.generation;
  if (targetView === 'library') closeReader(false);
  const startedAt = Date.now();
  if (targetView === view) queries[targetView] = $('#query').value;
  state.searched = queries[targetView].trim();
  if (targetView === 'library') state.mode = $('#mode').value;
  state.busy = true; state.paging = false; state.dirty = false;
  state.next = null; state.loadedCount = 0; state.completedAt = null; state.content.replaceChildren();
  const method = { keyword: 'words', hybrid: 'words + meaning', semantic: 'meaning' }[state.mode];
  message(targetView === 'library' && !state.searched ? 'Opening your collection…' : targetView === 'library' ? `Searching by ${method} across your collection…` : 'Opening your workspace…', '', state);
  syncView(state);
  try {
    const data = targetView === 'library' ? await api('search_library', { text: state.searched, mode: state.mode }) : targetView === 'research' ? await api('research_search', { text: state.searched }) : targetView === 'actions' ? await api('source_actions') : await api('media_requests');
    if (ticket !== state.generation) return;
    state.resultId = data.receipt.result_id;
    message('Loading result excerpts…', '', state);
    await page(false, state, ticket);
    if (ticket !== state.generation) return;
    const count = data.receipt.count;
    pendingUpdates.delete(targetView); updateNotice();
    state.total = count; state.completedAt = Date.now(); state.elapsed = state.completedAt - startedAt; state.effectiveMode = !state.searched && targetView === 'library' ? 'browse' : data.receipt.fallback ? 'keyword' : state.mode;
    message(`${count.toLocaleString()} ${targetView === 'actions' ? 'action' : targetView === 'media' ? 'review' : targetView === 'research' ? 'finding' : !state.searched ? 'source' : 'result'}${count === 1 ? '' : 's'}${state.searched ? ` for “${state.searched}”` : ''}${data.receipt.fallback ? ' · Meaning search isn’t available. Showing word matches.' : ''}${data.receipt.semantic_index?.workspace_revision_now > data.receipt.semantic_index?.enrichment_revision ? ' · New evidence is available; the meaning index needs a refresh.' : ''}`, '', state);
  } catch (error) {
    if (ticket !== state.generation) return;
    const missingIndex = /index_attachments|model|index.*(missing|unavailable)/i.test(error.message);
    message(missingIndex ? 'Meaning search isn’t ready yet. You can still search by words.' : /fetch/i.test(error.message) ? 'Couldn’t reach your workspace. Check that the local app is running.' : error.message, 'error', state);
    const box = el('div', null, 'empty-state');
    box.append(el('h2', 'Let’s try that again.'), el('p', 'Your collection is still here. Try the search again, or choose a different search method.'));
    if (targetView === 'library' && state.mode !== 'keyword') action(box, 'Search words instead', () => { $('#mode').value = 'keyword'; return load(); }, 'primary');
    else action(box, 'Retry', () => load(), 'secondary');
    state.content.replaceChildren(box);
  } finally {
    if (ticket === state.generation) { state.busy = false; state.loaded = true; syncView(state); }
  }
}
function switchView(nextView, updateHistory = true, autoLoad = true) {
  if (nextView === view) return;
  if (updateHistory) window.history?.pushState(null, '', {library:'#sources',research:'#notes',media:'#reviews',actions:'#actions'}[nextView]);
  queries[view] = $('#query').value;
  viewStates[view].scroll = window.scrollY;
  view = nextView;
  const state = viewStates[view];
  for (const button of document.querySelectorAll('[data-view]')) { if (button.dataset.view === view) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current'); }
  const [name, eyebrow, title, description] = views[view];
  $('#eyebrow').textContent = eyebrow; $('#page-title').textContent = title; $('#page-description').textContent = description;

  document.title = 'The Why-Did-I-Like-or-Save-That-inator · ' + name;
  $('#query').value = queries[view]; $('#query').required = false; $('#query').placeholder = view === 'research' ? 'Find a note or a finding…' : 'Search your collection'; $('#query').setAttribute('aria-label', view === 'research' ? 'Search your notes' : 'Search your sources');
  $('#mode-label').hidden = view !== 'library'; $('#search').hidden = view === 'media' || view === 'actions';
  $('#results').replaceChildren(state.content);
  syncView(state);
  if (autoLoad && (!state.loaded || state.dirty) && !state.busy && view !== 'library') load();
  window.scrollTo({ top: state.scroll, behavior: 'instant' });
  if (typeof window.setInterval === 'function') queueMicrotask(() => updateNotice());
}
$('#search-form').onsubmit = event => { event.preventDefault(); load(); };
$('#query').addEventListener('search', () => {
  if ($('#query').value) return;
  queries[view] = '';
  if (view !== 'library') { load(); return; }
  load();
});
$('#refresh-results').onclick = () => {
  const state = viewStates[view];

  load();
};
$('#more').onclick = async () => {
  const state = viewStates[view], ticket = state.generation;
  if (state.busy || state.paging || state.next == null) return;
  state.paging = true; syncView(state);
  try { await page(true, state, ticket); }
  catch (error) { if (ticket === state.generation) message(error.message, 'error', state); }
  finally { if (ticket === state.generation) { state.paging = false; syncView(state); } }
};
for (const link of document.querySelectorAll('[data-view]')) link.onclick = event => {
  if (event?.ctrlKey || event?.metaKey || event?.shiftKey || event?.altKey) return;
  event?.preventDefault();
  switchView(link.dataset.view);
};
function viewFromLocation() { switchView(({ '#notes':'research', '#reviews':'media', '#actions':'actions' })[window.location?.hash] || 'library', false); }
window.addEventListener?.('popstate', viewFromLocation);
viewFromLocation();
for (const button of document.querySelectorAll('[data-query]')) button.onclick = () => { $('#query').value = button.dataset.query; load(); };
$('#new-note').onclick = openNote;
$('#close-note').onclick = () => $('#note-dialog').close();
$('#close-media').onclick = () => $('#media-dialog').close();
$('#note-dialog').addEventListener('cancel', event => { if ($('#save-note').disabled) event.preventDefault(); });
$('#note-form').addEventListener('input', saveDraft);
$('#note-form').onsubmit = async event => {
  event.preventDefault(); const title = $('#title').value.trim(), text = $('#note').value.trim();
  if (!title || !text) { $('#note-status').textContent = 'Add a title and a note before saving.'; return; }
  const button = $('#save-note'); button.disabled = true; $('#note-status').textContent = 'Saving…';
  $('#title').readOnly = true; $('#note').readOnly = true; $('#close-note').disabled = true; $('#citation-list').inert = true;
  try {
    await durableWrite('note', 'save_note', { title, text, evidence });
    $('#note-form').reset(); evidence = []; pendingInvestigation = null; updateCitations(); saveDraft(); $('#note-dialog').close();
    viewStates.research.dirty = true;
    if (view === 'research') await load();
    message('Note saved. You’ll find it in Notes.');
  } catch (error) { $('#note-status').textContent = error.message; }
  finally { button.disabled = false; $('#title').readOnly = false; $('#note').readOnly = false; $('#close-note').disabled = false; $('#citation-list').inert = false; }
};
$('#media-form').onsubmit = async event => {
  event.preventDefault(); const objective = $('#media-objective').value.trim();
  if (!objective) { $('#media-status').textContent = 'Add a question for the review.'; return; }
  const button = event.submitter; button.disabled = true; $('#media-status').textContent = 'Queuing review…';
  try { if (!mediaSource) throw Error('Choose a captured source or attachment first.'); await durableWrite('queue-review', 'queue_review', { observation_id: mediaSource, objective }); $('#media-dialog').close(); viewStates.media.dirty = true; message('Review queued — waiting for a person or agent. Open the review queue for next steps.'); }
  catch (error) { $('#media-status').textContent = error.message; }
  finally { button.disabled = false; }
};
document.addEventListener('keydown', event => {
  if (event.key === '/' && !event.ctrlKey && !event.metaKey && !event.altKey && !['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName) && !event.target.isContentEditable && !document.querySelector('dialog[open]') && view !== 'media' && view !== 'actions') { event.preventDefault(); $('#query').focus(); }
});
try { const draft = JSON.parse(sessionStorage.getItem('gold-note-draft') || 'null'); if (draft) { $('#title').value = draft.title || ''; $('#note').value = draft.note || ''; evidence = Array.isArray(draft.evidence) ? draft.evidence : []; pendingInvestigation = draft.pendingInvestigation || null; updateCitations(); saveDraft(); } } catch { /* Ignore unavailable or obsolete draft storage. */ }
api('inventory').then(data => {
  $('#library-count').textContent = data.posts.toLocaleString();
  $('#collection-summary').textContent = `${data.posts.toLocaleString()} posts · ${data.sources.bookmarks.toLocaleString()} bookmarks · Local archive`;
  $('#inventory').textContent = `${data.posts.toLocaleString()} saved posts · ${data.sources.likes.toLocaleString()} likes · ${data.sources.bookmarks.toLocaleString()} bookmarks`;
  if (!viewStates.library.busy && !viewStates.library.loaded) load('library');
  if (!data.posts) { $('#welcome-title').textContent = 'A home for the things you save.'; $('.welcome > p').textContent = 'Sync from the Gold extension or import a backup to get started.'; $('.suggestions').hidden = true; }
}).catch(() => { $('#inventory').textContent = 'Workspace unavailable'; $('#collection-summary').textContent = 'Local archive unavailable'; message('Couldn’t open the workspace. Check that the local app is running, then reload.', 'error'); });


// Durable write attempts survive reloads. Replays use the same ID and input.
let pendingWrites = {};
try { pendingWrites = JSON.parse(sessionStorage.getItem('gold-pending-writes') || '{}'); } catch { /* Storage is optional. */ }
function persistWrites() { try { sessionStorage.setItem('gold-pending-writes', JSON.stringify(pendingWrites)); } catch { /* Retain in memory. */ } }
function requestId() { return globalThis.crypto?.randomUUID?.() || 'request-' + Date.now() + '-' + Math.random().toString(36).slice(2); }
async function durableWrite(slot, operation, args) {
  let attempt = pendingWrites[slot];
  if (attempt && (attempt.operation !== operation || JSON.stringify(attempt.args) !== JSON.stringify(args))) {
    const outcome = await api('action_outcome', { client_request_id: attempt.id });
    if (outcome.state !== 'committed') await api(attempt.operation, { ...attempt.args, client_request_id: attempt.id });
    delete pendingWrites[slot]; persistWrites();
    throw Error('Your earlier submission is saved. Your newer edits are still here; save again to submit them separately.');
  }
  if (!attempt) { attempt = pendingWrites[slot] = { id: requestId(), operation, args }; persistWrites(); }
  try {
    const result = await api(operation, { ...attempt.args, client_request_id: attempt.id });
    delete pendingWrites[slot]; persistWrites(); return result;
  } catch (error) {
    if (error.confirmed) { delete pendingWrites[slot]; persistWrites(); throw error; }
    const recovery = 'Connection interrupted. Checking whether the action was saved; your draft is retained…';
    if (slot === 'note') $('#note-status').textContent = recovery;
    else if (slot === 'queue-review') $('#media-status').textContent = recovery;
    else if (slot.startsWith('action-')) $('#action-status').textContent = recovery;
    else message(recovery);
    try {
      const outcome = await api('action_outcome', { client_request_id: attempt.id });
      if (outcome.state === 'committed') { delete pendingWrites[slot]; persistWrites(); return outcome.result; }
    } catch { /* The saved attempt remains available for a safe replay. */ }
    throw error;
  }
}

let pickerSource = null, pickerTargets = [], pickerGeneration = 0;
async function openMediaPicker(row) {
  pickerSource = row.observation_id; mediaSource = null;
  $('#media-form').reset(); $('#media-status').textContent = 'Loading source coverage…';
  $('#media-dialog').showModal(); await reloadTargets(); $('#media-target').focus();
}
async function reloadTargets() {
  if (!pickerSource) return;
  const ticket = ++pickerGeneration, source = pickerSource;
  $('#queue-review').disabled = true; $('#target-preview').replaceChildren();
  try {
    const result = await api('source_targets', { observation_id: source });
    if (ticket !== pickerGeneration) return;
    pickerTargets = result.targets; mediaSource = null;
    $('#media-target').replaceChildren(); const placeholder = el('option', 'Choose the source or attachment'); placeholder.value = ''; $('#media-target').append(placeholder);
    pickerTargets.forEach((t, index) => { const option = el('option', `${t.role === 'post' ? 'Saved post' : t.role.replaceAll('_', ' ')} · ${t.can_review ? 'Captured' : 'Not captured'} · ${t.url || 'Local evidence'}`); option.value = String(index); $('#media-target').append(option); });
    $('#media-target').value = ''; $('#media-status').textContent = 'Choose exactly what you want reviewed. Nothing is selected automatically.';
    $('#capture-target').hidden = true;
  } catch (error) { $('#media-status').textContent = error.message; }
}
function selectTarget() {
  const value = $('#media-target').value, t = value === '' ? null : pickerTargets[Number(value)];
  mediaSource = t?.can_review ? t.observation_id : null;
  $('#queue-review').disabled = !mediaSource;
  $('#capture-target').hidden = !t || t.can_review;
  const preview = $('#target-preview'); preview.replaceChildren();
  if (!t) return;
  preview.append(el('p', `${t.role.replaceAll('_',' ')} · ${t.coverage.replaceAll('_',' ')}`, 'coverage-note'));
  if (t.role === 'video_thumbnail') preview.append(el('p', 'This is a thumbnail, not the video. Import a transcript for spoken content.', 'review-warning'));
  if (t.image_available) { const image = el('img'); image.src = '/media/' + t.observation_id; image.alt = 'Selected captured image for review'; preview.append(image); }
  if (t.text) preview.append(el('p', t.text, 'post-text'));
  if (!t.can_review) preview.append(el('p', 'This attachment has not been captured. Capture it before asking Codex to inspect it. Access can fail; no content will be invented.'));
  sourceLink(preview, t.url);
}
$('#media-target').onchange = selectTarget;
$('#reload-targets').onclick = reloadTargets;
$('#capture-target').onclick = async () => {
  const t = pickerTargets[Number($('#media-target').value)];
  if (!t || !pickerSource) return;
  $('#capture-target').disabled = true;
  try { await beginWork('extract', JSON.stringify({ observation_id: pickerSource, url: t.url, role: t.role })); $('#media-status').textContent = 'Capture started. Track it in Activity, then Refresh coverage here.'; }
  catch (error) { $('#media-status').textContent = error.message; }
  finally { $('#capture-target').disabled = false; }
};

const reviewRunViews = new Map();
function providerName(provider) { return provider === 'claude' ? 'Claude Code' : 'Codex'; }
function draftText(run) {
  return run.result.description + ((run.result.uncertainties || []).length ? '\n\nLimitations: ' + run.result.uncertainties.join('; ') : '');
}
function syncReviewRunViews() {
  for (const [request, value] of reviewRunViews) {
    const run = currentRuns.find(r=>r.kind==='review' && r.target===request) || value.fallback;
    value.node.textContent = run ? providerName(run.provider) + ': ' + run.state + ' · ' + run.message : 'No agent run has been started for this request.';
    if (run?.state === 'ready' && value.draftRun !== run.id) {
      if (!value.draft) value.draft = disclosure(value.card, 'Agent draft — inspect before saving');
      const summary = value.draft.children[0];
      value.draft.replaceChildren(summary, el('p', run.result.description), el('p', (run.result.uncertainties || []).join(' · '), 'meta'));
      action(value.draft, 'Use this draft in the editor', () => {
        if (value.area.value.trim()) { value.status.textContent = 'Your existing edits are kept. Clear the editor first if you want to replace them with this draft.'; }
        else { value.area.value = draftText(run); value.status.textContent = 'Draft loaded. Check the analysis and limitations, then Save review.'; }
        value.area.focus(); value.area.scrollIntoView?.({block:'center'});
      });
      value.draftRun = run.id;
    }
  }
}
async function openReviewEditor(run) {
  switchView('media', true, false);
  const state = viewStates.media;
  if (state.busy || state.paging) throw new Error('The review queue is still loading. Try Open review editor again when it finishes.');
  if (!state.loaded) await load('media');
  let card = [...state.content.children].find(n => n._reviewId === run.target);
  while (!card && state.next != null) {
    await page(true, state);
    card = [...state.content.children].find(n => n._reviewId === run.target);
  }
  if (!card) throw new Error('This review is not in the loaded queue. Keep any edits, refresh the queue, then try again.');
  const editor = reviewRunViews.get(run.target);
  $('#activity').open = false;
  if (!editor) { card.scrollIntoView?.({block:'center'}); message('This review is already resolved.'); return; }
  syncReviewRunViews();
  if (editor.draft) editor.draft.open = true;
  if (!editor.area.value.trim()) { editor.area.value = draftText(run); editor.status.textContent = 'Draft loaded. Check the analysis and limitations, then Save review.'; }
  else editor.status.textContent = 'Your existing edits are kept. The agent draft is shown alongside the editor for comparison.';
  editor.area.focus(); editor.area.scrollIntoView?.({block:'center'});
}
let currentRuns = [], observedTokens = null, pendingUpdates = new Set(), pollBusy = false, runsSignature = '';
async function beginWork(kind, target, provider = 'codex') {
  const run = await durableWrite('work-'+kind+'-'+target+'-'+provider, 'start_work', { kind, target, provider });
  $('#activity').open = true;
  await refreshStatus();
  const latest = currentRuns.find(r => r.id === run.id) || run;
  if (['blocked','failed','interrupted'].includes(latest.state)) message(latest.message, 'error');
  else message('Work started. Activity shows progress, failures and recovery.');
  return run;
}
function renderRuns() {
  const host = $('#runs'); host.replaceChildren();
  for (const run of currentRuns.slice(0, 12)) {
    const card = el('article', null, 'run-status');
    card.append(el('h3', ({review:providerName(run.provider)+' review',index:'Meaning index',extract:'Attachment capture'})[run.kind] + ' · ' + run.state.replaceAll('_',' ')), el('p', run.message));
    card.append(el('p', 'Started ' + new Date(run.created*1000).toLocaleString() + ' · Last activity ' + new Date(run.last_event*1000).toLocaleTimeString(), 'meta'));
    if (['queued','starting','running'].includes(run.state)) action(card, 'Cancel work', async () => { await api('cancel_work', {run_id:run.id}); await refreshStatus(); }, 'text-button');
    if (['blocked','failed','interrupted','cancelled'].includes(run.state)) action(card, 'Retry work', () => beginWork(run.kind,run.target,run.provider || 'codex'), 'secondary');
    if (run.state === 'ready') {
      card.append(el('p', run.result.description), el('p', (run.result.uncertainties || []).join(' · '), 'meta'));
      action(card, 'Open review editor', () => openReviewEditor(run), 'secondary');
    }
    host.append(card);
  }
}
async function refreshStatus() {
  if (pollBusy) return; pollBusy = true;
  try {
    const status = await api('workspace_status');
    if (!status || !Array.isArray(status.runs)) return;
    const tokens = {library:status.sources_token, research:status.notes_token, media:status.reviews_token, actions:status.actions_token};
    if (observedTokens) for (const key of Object.keys(tokens)) if (tokens[key] !== observedTokens[key]) { pendingUpdates.add(key); viewStates[key].dirty = true; }
    const signature = JSON.stringify(status.runs.map(r => [r.id,r.state,r.message,r.result]));
    if (signature !== runsSignature) {
      if (currentRuns.length) { pendingUpdates.add('media'); viewStates.media.dirty = true; }
      currentRuns = status.runs; runsSignature = signature; renderRuns(); syncReviewRunViews();
    }
    observedTokens = tokens;
    $('#health-status').textContent = 'Connected · checked ' + new Date().toLocaleTimeString();
    const activeCount = currentRuns.filter(r=>['queued','starting','running'].includes(r.state)).length, attentionCount = currentRuns.filter(r=>['blocked','failed','interrupted'].includes(r.state)).length;
    $('#activity-count').textContent = [activeCount ? activeCount + ' running' : '', attentionCount ? attentionCount + ' need attention' : ''].filter(Boolean).join(' · ');
    $('#index-status').textContent = status.index_error || (!status.index ? 'Meaning search is not prepared. Word search is available.' : status.index.enrichment_revision == null ? 'A meaning index exists; its freshness has not been verified. Rebuild to establish its revision.' : status.index_stale ? 'New evidence is not in the meaning index yet. Rebuild when ready.' : 'Meaning index includes the current evidence revision.');
    $('#rebuild-index').disabled = currentRuns.some(r => r.kind==='index' && ['queued','starting','running'].includes(r.state));
    updateNotice();
  } catch (error) { $('#health-status').textContent = 'Status check failed: ' + error.message; }
  finally { pollBusy = false; }
}
function updateNotice() {
  $('#updates').hidden = !pendingUpdates.size;
  $('#updates-text').textContent = pendingUpdates.size ? 'Updates available in ' + [...pendingUpdates].map(k=>views[k][0]).join(', ') + '. Your reading position has been kept.' : '';
  $('#accept-updates').disabled = !pendingUpdates.has(view);
}
async function refreshPreservingReader() {
  const old = selectedCard, position = window.scrollY;
  await load(); pendingUpdates.delete(view); updateNotice();
  if (view === 'library' && old?._row) {
    const card = [...viewStates.library.content.children].find(n=>n._row?.observation_id===old._row.observation_id) || old;
    openReader(card._row,card,card._number,card._readTrigger);
  }
  window.scrollTo({top:position,behavior:'instant'});
}
$('#accept-updates').onclick = refreshPreservingReader;
$('#refresh-results').onclick = refreshPreservingReader;
$('#rebuild-index').onclick = async () => { try { await beginWork('index','library'); } catch (error) { message(error.message,'error'); } };
if (typeof window.setInterval === 'function') {
  refreshStatus(); window.setInterval(() => { if (!document.hidden) refreshStatus(); }, 5000);
  window.addEventListener('focus', refreshStatus);
}

let actionSource = null, actionVersion = 0;
async function openAction(row) {
  if (!row.next_action) row = await api('source_action', { observation_id:row.observation_id });
  actionSource = row.observation_id; actionVersion = row.version || 0;
  $('#action-form').reset(); $('#action-reason').value = row.reason || ''; $('#action-next').value = row.next_action || ''; $('#action-due').value = row.due_date || ''; $('#action-state').value = row.state || 'planned'; $('#action-outcome').value = row.outcome || '';
  $('#action-status').textContent = ''; $('#action-dialog').showModal(); $('#action-next').focus();
}
function renderAction(row, card) {
  card.append(el('h3', row.next_action), el('p', `${row.state === 'done' ? 'Done' : 'Planned'}${row.due_date ? ' · Due ' + row.due_date : ''}`, 'state-tag'));
  if (row.reason) card.append(el('p', 'Why: ' + row.reason));
  if (row.outcome) card.append(el('p', 'Outcome: ' + row.outcome));
  disclosure(card, 'Original captured source').append(el('p', row.source_text));
  action(card, 'Update action / record outcome', () => openAction(row), 'secondary');
}
$('#close-action').onclick = () => $('#action-dialog').close();
$('#action-dialog').addEventListener('cancel', event => { if ($('#save-action').disabled) event.preventDefault(); });
$('#action-form').onsubmit = async event => {
  event.preventDefault(); for (const id of ['action-reason','action-next','action-due','action-state','action-outcome']) $('#'+id).disabled = true; $('#save-action').disabled = true; $('#close-action').disabled = true; $('#action-status').textContent = 'Saving…';
  try {
    await durableWrite('action-'+actionSource, 'save_source_action', { observation_id:actionSource, reason:$('#action-reason').value, next_action:$('#action-next').value, due_date:$('#action-due').value, state:$('#action-state').value, outcome:$('#action-outcome').value, expected_version:actionVersion });
    $('#action-dialog').close(); viewStates.actions.dirty = true; if (view === 'actions') await load(); message('Action saved. Find it in Actions.');
  } catch (error) { $('#action-status').textContent = error.message; }
  finally { for (const id of ['action-reason','action-next','action-due','action-state','action-outcome']) $('#'+id).disabled = false; $('#save-action').disabled = false; $('#close-action').disabled = false; }
};
