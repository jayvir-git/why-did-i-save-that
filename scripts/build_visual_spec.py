"""Build/check the code-linked visual specification. No workspace data is read.

Edit the decisions and diagrams here, then run python scripts/build_visual_spec.py.
--check rejects stale generated documents, missing source anchors, and broken links.
Source evidence establishes behavior, not the historical reason for a decision.
"""
import argparse
import hashlib
import html
import inspect
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gold_workspace.interface import catalog
from gold_workspace.app import ALLOWED
from gold_workspace.engine import Workspace

UI = 'gold_workspace/web/app.js'
HTML = 'gold_workspace/web/app.html'
CSS = 'gold_workspace/web/app.css'
ENGINE = 'gold_workspace/engine.py'
RESEARCH = 'gold_workspace/research.py'
SEARCH = 'gold_workspace/attachment_search.py'
JOBS = 'gold_workspace/jobs.py'
UITEST = 'tests/workspace-ui.test.cjs'
PYTEST = 'tests/test_research.py'

# ID, area, title, observed rule, consequence, acceptance example, file, source anchor.
RULES = [
('D01','Capture','Capture is explicitly enabled','Only eligible X history traffic is observed while collection is enabled.','A saved library is not proof that the entire historical account was collected.','Pause collection; a response that was already in flight must not add posts.','extension/network.js','function eligible'),
('D02','Capture','Identity includes the account','Normalized keys distinguish the same post saved by different owners.','Merging accounts would lose who saved what.','Capture the same post for two owners; retain two distinct keys.','extension/core.js','function normalize'),
('D03','Capture','Recapture merges evidence','Recapture can improve text and media while preserving review decisions.','Capturing again should not erase a human classification.','Recapture a reviewed post; confirmed and rejected reasons survive.','extension/core.js','function merge'),
('D04','Capture','Sync is a separate operation','The extension sends local posts in batches of 200 to the authenticated bridge.','Browser storage and the workspace can disagree until sync succeeds.','An unavailable bridge produces a saved sync error, not a successful sync status.','extension/workspace-sync.js','async function syncWorkspace'),
('D05','Capture','Ingestion is authenticated','The bridge accepts backup ingestion on loopback with a pairing token.','Pairing authorizes ingestion; it is not permission to execute arbitrary commands.','A request without the token is rejected.','gold_workspace/bridge.py','def do_POST'),
('D06','Evidence','Import is validated and versioned','Imports validate identities and retain immutable observations; repeated backup content is idempotent.','New captures create versions rather than rewriting old citation targets.','Import the same backup twice; the second import adds no versions.',ENGINE,'def import_backup'),
('D07','Evidence','Snapshots and results are stable','Search results are materialized in SQLite under result IDs.','Later imports do not change pages belonging to an existing result set.','Import new content between pages; the old result ID still returns its original rows.',ENGINE,'def _result'),
('D08','Sources','Browse has a defined order','Empty search text browses current posts by posted date descending, with undated posts last.','Browse is chronological, not ranked by relevance or save date.','An undated post follows dated posts; semantic inference is not called.',RESEARCH,'def search_library'),
('D09','Search','Word matching is token based','Unicode word tokens are case-folded; a query can match any query term, ranked by BM25.','Words only is neither exact phrase matching nor an all-words requirement.','A two-term query may return a source containing only one term.',RESEARCH,'query = set(terms(text))'),
('D10','Search','Word search includes captured evidence','Search includes post text, context, quotes and extracted attachment text, deduplicating identical source text within a document.','Unfetched pages and uninterpreted pixels cannot contribute text matches.','An imported transcript phrase becomes a word match.',RESEARCH,'def lexical_index'),
('D11','Search','Warm word data is shared','A bounded process cache reuses token counts and postings across HTTP connections; revisions and attachment relationships invalidate it.','First load and changed evidence still require preparation. Separate CLI processes do not share it.','Two connections searching unchanged data construct the corpus once; import then rebuilds it.',RESEARCH,'stamp = (w.revision()'),
('D12','Search','Meaning search uses a pinned index','Local passage search uses an immutable attachment index selected by a pointer or explicit ID.','A valid meaning index may omit evidence captured after it was built.','New evidence changes word search immediately but does not silently alter an old semantic index.',SEARCH,'def search'),
('D13','Search','Passages have bounded overlap','Indexing covers cleaned text in 120-word windows with 30-word overlap and exact original spans.','Cleaning affects matching, not the original quoted evidence.','A phrase near the end of a long document remains represented.',SEARCH,'def passages'),
('D14','Search','Meaning scores do not prove truth','Parent ranking uses maximum passage cosine and up to three distinct supporting excerpt texts.','Similarity is a retrieval signal, not a confidence or truth score.','Shared attachment evidence does not multiply a parent score.',SEARCH,'selected = []; seen = set()'),
('D15','Search','Hybrid combines ranks','Words + meaning adds reciprocal ranks with k=60; ties use observation ID.','The displayed order does not use a learned reranker.','A source present in both ranked lists receives both reciprocal-rank contributions.',RESEARCH,"target['score'] += 1/(60+rank)"),
('D16','Search','Hybrid failure degrades explicitly','Known model, filesystem and index errors fall back to lexical results in hybrid mode; semantic-only mode raises the error.','A word-only result is useful, but must not be called successful meaning search.','Make model assets unreadable; hybrid returns word results and a fallback receipt.',RESEARCH,'except (RuntimeError, OSError, ValueError)'),
('D17','Search','Semantic data is cached','Up to two indexes are reused; NumPy scores normalized matrices when available.','Cold JSON loading and model initialization remain different from warm scoring.','Search through two workspace connections; unchanged index data is loaded once.',SEARCH,'@functools.lru_cache(maxsize=2)'),
('D18','Sources','Search replaces the visible list','Submitting a query clears the previous list and reader, then retrieves a result ID and a first page.','A failed new search does not leave the old results visible as if they answered it.','Submit a new query while reading; selection clears and pending feedback appears.',UI,'async function load'),
('D19','Sources','Late responses are ignored','Generation tickets and result IDs prevent an older request from replacing a newer view.','Ignoring a response does not cancel server work.','An old query finishes last; the newer query remains on screen.',UI,'ticket !== state.generation'),
('D20','Sources','Pages contain 20 rows','The UI loads 20 rows at a time from a stable result ID.','Loaded count and total count have different meanings.','Load more appends rows and continues ordinals.',UI,"offset: append ? state.next : 0, limit: 20"),
('D21','Navigation','Tabs preserve local state','Queries, results, scroll position and source selection are retained while this page is open.','Switching tabs is not a freshness check.','Return from Notes to Sources without rerunning the source search.',UI,'function switchView'),
('D22','Navigation','Refresh is explicit','Refresh starts a new request; note and review actions mark relevant destinations dirty.','Externally completed work does not automatically refresh the open UI.','Complete a review externally; Refresh is required to see the current status.',UI,"$('#refresh-results').onclick"),
('D23','Navigation','URLs identify destinations','Sources, Notes and Reviews have hash destinations with Back navigation support.','Individual posts and notes do not have dedicated deep links here.','Open #notes directly and use browser Back between destinations.',UI,'function viewFromLocation'),
('D24','Sources','Scan and Read reuse results','Changing density alters presentation without retrieving again; preference uses localStorage.','Layout preference survives when browser storage is available.','Toggle Scan/Read and verify zero API calls.',UI,'function setDensity'),
('D25','Sources','Reading preserves full post text','Cards bound post text at 600 characters; the reader uses the full captured post.','Full captured post text is not necessarily the complete original remote post.','Open a long source; the reader retains the tail.',UI,'reading ? text : text.slice(0, 600)'),
('D26','Sources','Excerpts and citations differ','The match preview is bounded at 360 characters; stored evidence retains its exact quote and offsets.','A shortened visual preview must not become the citation text.','Add a long excerpt to a note; the citation retains the full source span.',UI,"quote.length > 360"),
('D27','Sources','Scan hides secondary actions','In the Sources scan layout, evidence and actions other than Read post are hidden by CSS.','Keeping evidence and requesting a review requires opening the reader or changing layout.','Open Read post from Scan to reveal the source actions.',CSS,'.library-view .scan-view .library-result .actions button:not(.post-toggle)'),
('D28','Evidence','Evidence kinds are labelled','The UI distinguishes post text, linked pages, OCR, thumbnail OCR, transcripts and interpretation.','A thumbnail does not establish what happens in the full video.','Thumbnail OCR receives an explicit thumbnail-only label.',UI,'function passageLabel'),
('D29','Evidence','Missing information is explicit','Missing post text, absent dates and unavailable excerpts receive explanatory copy.','Absence of captured information does not prove that the source has no such content.','An undated record says Date unavailable.',UI,"'Date unavailable'"),
('D30','Notes','Citations are exact source spans','Add to note collects supporting spans, deduplicated by observation, field and offsets; citations can be removed.','A note may combine evidence from several results.','Add the same span twice; retain one citation.',UI,'function addToNote'),
('D31','Notes','Draft storage is tab scoped','Title, body, citations and pending investigation ID are stored in sessionStorage when available.','Reload recovery is not durable backup; another device or closed session may not retain it.','Reload the same session and recover a draft; storage failure leaves editing usable.',UI,'function saveDraft'),
('D32','Notes','A note save has two writes','The UI creates an investigation, then saves an artifact or cited claim.','The action is not one atomic server transaction; partial completion is possible.','Fail the second request; retain the draft and pending investigation ID.',UI,'if (!pendingInvestigation)'),
('D33','Notes','Citation fidelity is validated','Claims verify the exact source field, offsets and quote before writing an artifact version.','Quotation fidelity does not establish that the source supports the conclusion.','A changed quote is rejected, even when the observation ID is valid.',ENGINE,'def claim'),
('D34','Notes','Versions prevent blind overwrites','Artifact writes check expected_version and append a new version.','Conflicting edits require reconciliation rather than last-writer-wins.','Reuse an obsolete version; receive a conflict.',ENGINE,'def artifact'),
('D35','Notes','UI note states remain qualified','Uncited notes are saved as unverified; cited claims from this UI are proposed.','Adding a citation does not mark a finding as verified.','Inspect the saved status of both note types.',UI,"status: 'proposed'"),
('D36','Notes','Saving locks the editor','During save, the button, editor and citation controls are locked; failure restores them and retains the draft.','A user cannot edit the submitted draft while its request is pending.','A returned usage error leaves the draft intact and Save enabled.',UI,"$('#title').readOnly = true"),
('D37','Notes','Research is separate from sources','Research search returns latest artifact versions and flags changed captured evidence.','Newer archive content and changed cited evidence are distinct warnings.','Recapture a cited source; the finding displays the changed-source warning.',RESEARCH,'def research_search'),
('D38','Reviews','Review target is chosen automatically','Request media review selects the first non-post supporting passage, falling back to the post.','With several attachments, the selected target may not be the one the user intended.','Inspect the submitted observation ID on a result with multiple attachments.',UI,"find(p => p.role !== 'post')"),
('D39','Reviews','Queueing is durable, not execution','request_media stores a pending request; equal pending observation/objective pairs reuse a request.','No provider, runner or execution acknowledgment is created.','Queue a request; it remains pending until someone explicitly completes it.',RESEARCH,'def request_media'),
('D40','Reviews','External agent state is unknown','The app has no Codex usage/status connection and does not automatically start an agent.','Quota failures elsewhere cannot be inferred from a pending row.','Stop an external agent; the app must not invent running or failed state.',UI,'This app cannot check external agent progress'),
('D41','Reviews','Completion adds derived evidence','Completing a pending request stores visual analysis or transcript as a separate resource, then marks it completed with a new version.','Original source text is retained; word search sees derived evidence; meaning search needs reindexing.','Complete a review; search its phrase while preserving original text.',RESEARCH,'def complete_media'),
('D42','Reviews','Completion checks version and state','Only a pending request at the expected version can be completed.','Repeated or racing completion can return a conflict; completion is not a provider retry mechanism.','Complete the same request twice; the second call is rejected.',RESEARCH,"if not row or row['version']!=expected_version"),
('D43','Reviews','Cancelled is not an exposed transition','media_requests accepts a cancelled filter, but this checkout exposes no operation to cancel a media request.','Do not draw a working Cancel review button in the current-state map.','Catalog inspection finds cancel_job but no cancel_media operation.',RESEARCH,"if state not in ('all','pending','completed','cancelled')"),
('D44','Failures','Every UI API request has a deadline','Each API call races a 30-second timer; timeout aborts browser waiting and restores controls.','A multi-call action can take more than 30 seconds overall; server work may still finish.','A fetch that never settles produces a visible timeout and releases controls.',UI,'}, 30000)'),
('D45','Failures','Returned errors have explanations','Network, malformed-response and returned quota errors become readable messages.','Quota wording only applies when an error actually reaches this app.','Return a quota payload; display account/reset guidance without claiming automatic detection.',UI,'function requestError'),
('D46','Failures','Writes are not automatically retried','Timeout guidance asks users to refresh before retrying a save.','Unknown outcome is different from a confirmed failed write.','Simulate response loss after commit; reconcile the saved result before submitting again.',UI,'If you were saving, refresh first'),
('D47','Jobs','Jobs are separate from review requests','Background jobs support fetch, asset, embed and imported text tasks through Python/CLI/MCP.','The Review queue is not a job monitor and does not expose these controls.','Compare job and media request IDs, states and catalogs.',JOBS,'def create_job'),
('D48','Jobs','Workers lease and checkpoint','A worker leases a job for 300 seconds and checkpoints results/errors per item; operation keys support replay.','Another active worker is rejected; recovery is different from an automatic scheduler.','A second worker cannot acquire an unexpired lease.',JOBS,'lease_until=time.time()+300'),
('D49','Jobs','Terminal states reflect item outcomes','Exhausted jobs become completed, partial or failed; unfinished bounded runs return to pending.','Some successful evidence can exist in a partial job.','One successful and one failed item ends in partial, not completed.',JOBS,"state=('partial'"),
('D50','Jobs','Cancel and retry preserve history','Cancellation retains completed evidence; resume=true can restart cancelled work; retry creates a new job of failed items.','Retry does not rewrite the original failed job history.','Cancel after one item and resume; completed work is retained.',JOBS,'def retry_job'),
('D51','Boundaries','Web API is deliberately narrower','The local web app uses an explicit operation allowlist and same-origin JSON checks.','CLI/MCP capability does not imply a corresponding UI button.','Sending an operation outside ALLOWED to /api is rejected.','gold_workspace/app.py','ALLOWED ='),
('D52','Boundaries','Static files are restricted','The app serves explicit web assets and supported cached images, not arbitrary workspace files.','A blob path or database filename is not a public asset URL.','Request the workspace database path through HTTP; receive no database.','gold_workspace/app.py','assets={'),
('D53','Boundaries','Source text is not trusted markup','UI construction uses textContent for captured source text and restricts source links to HTTP(S).','A captured HTML snippet should appear as text rather than execute.','Render source text containing a script tag; no script runs.',UI,'node.textContent = text'),
('D54','Boundaries','Fetches target public destinations','The public fetcher validates addresses and redirects and bounds downloads.','Failed access remains missing evidence; it is not silently bypassed.','A private-network destination is rejected.','gold_workspace/fetching.py','def validate_url'),
('D55','Recovery','Backup is explicit','The backup script uses SQLite backup plus workspace files and excludes token-named files.','Local persistence alone is not a scheduled backup or cross-device copy.','Restore a generated archive; research remains and the pairing token does not.','scripts/backup_workspace.py','def backup'),
('D56','Presentation','Small interface decisions have sources','UI design rules describe navigation, identity, typography, reading hierarchy and responsive behavior; CSS contains exact values.','A diagram cannot establish the historical rationale for every pixel. Unrecorded rationale stays unknown.','Check desktop and narrow layouts against docs/ui-design.md; do not claim automated visual coverage.',CSS,':root'),
('D57','Accessibility','Keyboard and focus behavior are explicit','The UI has a skip link, native dialogs, source-reader focus return and a slash-to-search shortcut.','These are implemented mechanisms, not a completed accessibility audit.','Use only the keyboard to open and leave the reader; focus returns to its trigger.',UI,"$('#close-reader').focus()"),
('D58','Presentation','Build version is checked','Release checks validate the displayed app version and extension script paths.','The version plate is not evidence of the running server process having reloaded changes.','Change the plate without package metadata; the check rejects it.','scripts/check.cjs','app-version'),
('D59','Capture','Classification is a browser workflow','The extension has kept/dismissed decisions, suggested reasons and undo, separate from Sources/Notes.','Suggested content categories do not prove why the person saved a post.','Reject a suggestion and recapture; the rejected reason stays rejected.','extension/library.js','async function decide'),
('D60','Search','No live performance promise exists','Search receipts describe methods and counts; tests cover fixtures, not a production latency budget or relevance benchmark.','Warm measurements do not establish cold latency, p95 latency or retrieval quality.','Define labelled queries and cold/warm budgets before calling search fast and accurate.','TESTING.md','not a benchmark proving retrieval quality'),
]

# Updated contracts after implementing the improvement pass.
WORKFLOWS = 'gold_workspace/workflows.py'
OVERRIDES = {
 'D21':('Tabs retain results, query drafts, scroll and the selected source. A five-second status poll offers updates without replacing them.','Refresh is explicit; the update action preserves the selected source reader and reading position.','Detect external evidence while reading; the reader stays selected.',UI,'async function refreshPreservingReader'),
 'D22':('Status polling compares source, note, review and action tokens and offers a refresh notice.','The app observes committed local changes; it does not infer remote source changes.','Complete a review externally; show an update notice without replacing the reader.',UI,'async function refreshStatus'),
 'D23':('Sources, Notes, Reviews and Actions have hash destinations and browser Back support.','Individual records still do not have dedicated deep links.','Open #actions directly and navigate Back.',UI,'function viewFromLocation'),
 'D32':('save_note commits investigation, artifact and stable request receipt in one transaction.','A lost acknowledgment can be reconciled and replayed without duplicating the note.','Drop the response after commit; one note exists and its receipt resolves.',WORKFLOWS,'def save_note'),
 'D35':('Uncited notes are unverified; cited notes are proposed after exact-span validation.','Citations do not establish truth automatically.','Inspect the stored status of a cited and an uncited note.',WORKFLOWS,'def save_note'),
 'D38':('Review and coverage opens an explicit source/attachment selector with no default selection.','Missing attachments must be captured before they can be reviewed; displayed previews identify the target.','Choose attachment B among multiple references; the submitted observation is B.',UI,'async function openMediaPicker'),
 'D39':('queue_review records a pending request with a replayable receipt. Starting Codex is a separate explicit action.','Queueing still does not silently spend agent usage.','Queue a source, then start one tracked run explicitly.',WORKFLOWS,'def queue_review'),
 'D40':('Runs started here use the local Codex CLI and persist actual acknowledgment, failures, heartbeat and draft results.','Externally started agents remain unobserved. Missing sign-in and quota failures are blocked states, not silent pending work.','A provider quota failure persists as blocked across page reload.', 'gold_workspace/runner.py','def run_codex'),
 'D41':('save_review atomically commits derived evidence, completion, annotation and request receipt. Codex output is a draft until the user saves it.','Words see new evidence; the meaning index needs a rebuild. Original text is retained.','Retry a committed completion with the same request ID; no second resource is created.',WORKFLOWS,'def save_review'),
 'D42':('Completion checks pending state and expected version. Identical request-ID replays return the original committed result.','A different conflicting completion is rejected; an acknowledged replay is not a conflict.','Replay the same completion, then submit a conflicting one.',WORKFLOWS,'def save_review'),
 'D45':('The UI explains request errors; tracked workers additionally persist quota, sign-in, runtime, cancellation and interruption outcomes.','Only observed provider failures are described as provider failures.','Inject a quota failure; show blocked status and a retry action.','gold_workspace/runner.py','def failure'),
 'D46':('After an interrupted write, the UI checks its receipt; an unchanged retry reuses the original ID and payload.','A missing receipt can mean still in flight; replaying the same ID serializes with that write. Edited content resolves the earlier attempt first.','Lose a committed save response; recover it without another note.',UI,'async function durableWrite'),
 'D60':('A repeatable synthetic HTTP benchmark reports fresh-process and warm p50/p95 plus expected-source hit@5. Initial fixture budgets are 2500ms cold and 500ms warm.','The fixture is a regression baseline, not proof of personal-library relevance or semantic latency.','Run the benchmark and fail on budget, hit@5 or fallback violations.','scripts/benchmark_search.py','def main'),
}
RULES = [(*r[:3],*OVERRIDES[r[0]]) if r[0] in OVERRIDES else r for r in RULES]
RULE_TITLES={'D32':'A note save is atomic','D38':'The person selects the review target','D40':'Tracked agent execution is observable','D41':'Accepted drafts become derived evidence','D42':'Completions support safe replay','D46':'Uncertain writes reconcile safely','D60':'Search has measurable fixture budgets'}
RULES=[(*r[:2],RULE_TITLES.get(r[0],r[2]),*r[3:]) for r in RULES]
RULES += [
 ('D61','Actions','Saves can lead to recorded outcomes','An action records a user-authored reason, next step, optional due date and completion evidence against an immutable source.','One action exists per captured source observation; completion requires an outcome.','Mark done without an outcome and receive validation; add outcome and save.',WORKFLOWS,'def save_source_action'),
 ('D62','Reviews','Workers have observable lifecycles','Tracked work can be queued, starting, running, ready, succeeded, blocked, failed, interrupted or cancelled. Heartbeats older than 45 seconds are interrupted.','A ready Codex draft is not completed review evidence. Extraction or index work can succeed separately.','Cancel a run; a late result must not change it to ready.',WORKFLOWS,'def work_status'),
 ('D63','Evidence','Coverage has repair actions','Coverage enumerates all referenced attachments and offers explicit capture; Activity offers a tracked meaning-index rebuild.','Optional local extraction/model dependencies and remote access can fail visibly. There is no built-in speech transcription.','Capture a referenced URL and refresh coverage; refuse a URL unrelated to the source.',WORKFLOWS,'def source_targets'),
 ('D64','Recovery','Receipts bind IDs to exact input','Each new UI write retains a stable request ID and input until its outcome is known. Different input with the same ID is rejected.','Concurrent retries cannot create duplicate atomic note saves. Legacy direct artifact APIs retain their older version semantics.','Submit the same note concurrently through two connections; one artifact commits.',WORKFLOWS,'def _receipt'),
 ('D65','Accessibility','Product workflows have browser checks','A real disposable HTTP workspace is tested in Edge for attachment selection, lost acknowledgments, failure visibility, outcomes, source preservation, keyboard focus and narrow layouts.','These tests do not constitute a complete assistive-technology audit.','Run check_workflows.cjs with Playwright and inspect its failure output.','scripts/check_workflows.cjs','const {chromium}'),
 ('D66','Boundaries','Codex receives only the selected input','A Codex review runs ephemerally in a temporary directory with a read-only sandbox and no user configuration. Only selected text and a supported cached image are supplied.','The selected source is sent to the signed-in provider and consumes account usage. The UI explains this at the Start action.','Inspect the spawned argument vector and prompt; no whole-library prompt or workspace-write permission.','gold_workspace/runner.py',"args=[executable,'exec'"),
]

TESTS = {
 'D01':('tests/network.test.cjs','pause discards responses'), 'D02':('tests/core.test.cjs','same post in two accounts'),
 'D03':('tests/core.test.cjs','recapture merges'), 'D04':('tests/workspace-sync.test.cjs','workspace sync sends every post'),
 'D05':('tests/test_bridge.py','def test_authentication'), 'D06':('tests/test_workspace.py','def test_idempotent'),
 'D07':('tests/test_workspace.py','def test_snapshots'), 'D08':(PYTEST,'def test_browse'),
 'D11':(PYTEST,'def test_queries_reuse'), 'D12':('tests/test_attachment_search.py','def test_shared_attachment'),
 'D13':(PYTEST,'def test_full_document'), 'D16':(PYTEST,'def test_unreadable_model'),
 'D17':('tests/test_attachment_search.py','def test_index_is_reused'), 'D18':(UITEST,'Browse all clears'),
 'D19':(UITEST,'a late search response'), 'D20':(UITEST,'result ordinals'), 'D21':(UITEST,'returning to Library'),
 'D22':(UITEST,'explicit refresh'), 'D23':(UITEST,'destination links'), 'D24':(UITEST,'changing Scan/Read'),
 'D28':(UITEST,'thumbnail OCR'), 'D33':('tests/test_workspace.py','def test_claim_span'),
 'D34':('tests/test_workspace.py','def test_claim_span'), 'D36':(UITEST,'failed note saves'),
 'D37':(PYTEST,'def test_research_versions'), 'D39':(PYTEST,'def test_media_import'),
 'D40':(UITEST,'pending reviews explain'), 'D41':(PYTEST,'def test_completion_invalidates'),
 'D42':(PYTEST,'def test_media_import'), 'D44':(UITEST,'a request that never responds'),
 'D45':(UITEST,'usage errors explain'), 'D48':('tests/test_workspace.py','def test_live_lease'),
 'D49':('tests/test_workspace.py','def test_jobs_checkpoint'), 'D50':('tests/test_workspace.py','def test_jobs_checkpoint'),
 'D51':(PYTEST,'def test_web_rejects'), 'D52':(PYTEST,'def test_web_rejects'),
 'D54':('tests/test_workspace.py','def test_public_fetch'), 'D55':(PYTEST,'def test_workspace_backup'),
 'D59':('tests/discovery.test.cjs','recapture preserves rejected'),
}

TESTS.update({
 'D21':('scripts/check_workflows.cjs','Polling notices external evidence'),
 'D22':('scripts/check_workflows.cjs','Polling notices external evidence'),
 'D32':('tests/test_workflows.py','def test_atomic_note_replay'),
 'D38':('scripts/check_workflows.cjs',"await page.selectOption('#media-target','2')"),
 'D39':('tests/test_workflows.py','def test_review_completion'),
 'D40':('tests/test_workflows.py','def test_worker_persists_provider_failure'),
 'D41':('tests/test_workflows.py','def test_review_completion'),
 'D42':('tests/test_workflows.py','def test_review_completion'),
 'D45':('tests/test_workflows.py','def test_quota_and_auth'),
 'D46':('scripts/check_workflows.cjs','drop its HTTP acknowledgment'),
 'D60':('scripts/benchmark_search.py',"result['passed']"),
 'D61':('tests/test_workflows.py','def test_actions_require_outcomes'),
 'D62':('tests/test_workflows.py','def test_cancelled_run'),
 'D63':('tests/test_workflows.py','def test_targets_include'),
 'D64':('tests/test_workflows.py','def test_concurrent_save'),
 'D65':('scripts/check_workflows.cjs','320px overflow'),
 'D66':('tests/test_workflows.py',"self.assertIn('read-only'"),
})

# Nodes: ID, label, decision IDs, owner, persisted object. Edges: from, to, trigger.
DIAGRAMS = [
 {'id':'journey','title':'From saving to using','question':'What does the app help a person finish?',
  'nodes': [('capture','Capture saves',['D01','D02','D03'],'Person + extension','Browser library'),('sync','Sync archive',['D04','D05','D06'],'Extension + bridge','Immutable observations'),('find','Find a source',['D08','D09','D12'],'Person + local server','Result snapshot'),('read','Inspect evidence',['D25','D28','D29'],'Person','Selection in this page'),('note','Keep a finding',['D30','D32','D33'],'Person + local server','Investigation + artifact'),('review','Request deeper inspection',['D38','D39','D40'],'Person + external reviewer','Pending media request'),('outcome','Use it and record an outcome',[],'Proposed: person','No dedicated outcome record')],
  'edges':[('capture','sync','Sync succeeds'),('sync','find','Browse or submit query'),('find','read','Read post'),('read','note','Add to note'),('read','review','Question needs more evidence'),('review','note','Reviewer supplies findings'),('note','outcome','Proposed next-action workflow')],
  'gap':'The archive supports retrieval and notes. A structured next action, due date, and finished outcome are not a dedicated workflow here.'},
 {'id':'reviews','title':'Review requests are not agent runs','question':'What is actually happening after Request review?',
  'nodes':[('choose','Target chosen automatically',['D38'],'Browser controller','Observation ID'),('submit','Submit objective',['D39','D44'],'Person + API','Pending request if committed'),('pending','Pending / waiting',['D39','D40'],'Person or external agent','media_requests.state=pending'),('unknown','External progress unknown',['D40'],'Outside this app','No run ID, heartbeat or quota event'),('complete','Submit analysis or transcript',['D41','D42'],'Person / external agent','Derived resource + versioned completion'),('visible','Reviewed after refresh',['D22','D41'],'Browser + server','Completed request and evidence')],
  'edges':[('choose','submit','Request media review'),('submit','pending','Server acknowledges'),('pending','unknown','External work may occur; unobserved'),('pending','complete','Explicit complete_media call'),('complete','visible','Refresh queue'),('submit','unknown','Response lost: write outcome unknown')],
  'gap':'No running, quota-blocked or failed agent-run state can be derived from this queue. A cancelled filter exists, but no exposed media-cancel operation exists.'},
 {'id':'search','title':'Search has two evidence clocks','question':'Which data can this query see?',
  'nodes':[('input','Submit query or browse',['D08','D18'],'Browser','Query draft'),('words','Current word index',['D09','D10','D11'],'Local server','Revision-sensitive memory cache'),('meaning','Pinned meaning index',['D12','D13','D17'],'Local model + server','Immutable index on disk'),('rank','Rank or combine results',['D14','D15','D16'],'Local server','Word, semantic or fused ranking'),('snapshot','Store result snapshot',['D07'],'Local server','SQLite result ID'),('page','Fetch 20-row page',['D19','D20'],'Browser + server','Stable paging cursor'),('error','Fallback or visible error',['D16','D44','D45'],'Browser + server','No implied semantic success')],
  'edges':[('input','words','Words / hybrid'),('input','meaning','Meaning / hybrid'),('words','rank','BM25 ranks'),('meaning','rank','Cosine ranks'),('meaning','error','Known index/runtime failure'),('error','rank','Hybrid only: word fallback'),('rank','snapshot','Materialize rows'),('snapshot','page','result(result_id, offset, 20)')],
  'gap':'Current lexical evidence and older semantic evidence can be fused. Cold preparation cost and relevance quality need separate acceptance criteria.'},
 {'id':'notes','title':'A save can have an unknown outcome','question':'What survives a failed or interrupted save?',
  'nodes':[('draft','Draft + exact citations',['D30','D31'],'Person + browser','Session storage when available'),('locked','Submit and lock editing',['D36','D44'],'Browser','Draft retained'),('investigation','Create investigation',['D32'],'Server','Investigation ID'),('artifact','Write note or claim',['D33','D34','D35'],'Server','Append-only artifact'),('saved','Success: clear draft',['D36','D37'],'Browser','Saved note remains in workspace'),('retry','Error: retain draft',['D36','D45'],'Browser','Editable draft and known ID'),('uncertain','Timeout: reconcile first',['D32','D46'],'Person + server','Commit may have happened')],
  'edges':[('draft','locked','Save note'),('locked','investigation','No pending ID'),('investigation','artifact','ID received'),('locked','artifact','Pending ID already known'),('artifact','saved','Acknowledgment received'),('artifact','retry','Confirmed error received'),('investigation','uncertain','Response lost'),('artifact','uncertain','Response lost')],
  'gap':'There is no client request ID that reconciles a lost write acknowledgment. A retained draft can coexist with a committed note.'},
 {'id':'evidence','title':'Evidence is not interpretation','question':'What can a displayed finding legitimately claim?',
  'nodes':[('post','Captured post / quote',['D06'],'Collector + import','Immutable source observation'),('asset','Fetched attachment',['D10','D54'],'Enrichment worker','Separate resource observation'),('text','Extracted text / OCR',['D13','D28'],'Extractor','Derived text with coverage'),('interpretation','Analysis / transcript',['D40','D41'],'Person / external agent','Separate derived resource'),('span','Exact excerpt',['D26','D30','D33'],'Retrieval + citation validator','Observation + field + offsets'),('claim','Proposed finding',['D33','D35','D37'],'Person / agent','Artifact with evidence links')],
  'edges':[('post','asset','Referenced URL, if fetch succeeds'),('asset','text','Supported extraction'),('asset','interpretation','Explicit inspection or import'),('post','span','Captured text'),('text','span','Extracted text'),('interpretation','span','Labelled derived evidence'),('span','claim','Validate quotation fidelity')],
  'gap':'Exact quotation validation does not establish semantic support. Unfetched, untranscribed and visually uninspected material stays outside known coverage.'},
 {'id':'jobs','title':'Background job state machine','question':'How do partial work, retries and cancellation behave?',
  'nodes':[('pending','Pending',['D47'],'CLI / MCP caller','Job payload + cursor'),('running','Running with lease',['D48'],'Bounded worker','Lease + item checkpoints'),('complete','Completed',['D49'],'Worker','All items processed without error'),('partial','Partial / failed',['D49'],'Worker','Results and error list'),('cancelled','Cancelled',['D50'],'Explicit caller','Completed evidence retained'),('retry','New retry job',['D50'],'Explicit caller','Failed items copied to new job')],
  'edges':[('pending','running','run_job acquires lease'),('running','pending','Batch ends; items remain'),('running','complete','All done; no errors'),('running','partial','All done; errors exist'),('running','cancelled','cancel_job'),('pending','cancelled','cancel_job'),('cancelled','running','run_job(resume=true)'),('partial','retry','retry_job'),('retry','running','run_job on new ID')],
  'gap':'These are local enrichment jobs. They are not Codex agent runs, and this state machine is not exposed in the Sources/Notes UI.'},
 {'id':'boundaries','title':'Storage and execution boundaries','question':'Where does data live, and who can act on it?',
  'nodes':[('extension','Chrome extension',['D01','D04','D59'],'User browser','Browser-local library + preferences'),('bridge','Loopback ingestion :8766',['D05'],'Python bridge','Pairing token + imports'),('store','Workspace data',['D06','D07','D55'],'Local filesystem / SQLite','Observations, blobs, notes, jobs, results'),('web','Sources / Notes :8768',['D51','D52','D53'],'Local web app','Transient view state + draft'),('external','External agent via CLI/MCP',['D40','D47','D51'],'User-selected agent','Agent-owned execution context'),('backup','Explicit backup archive',['D55'],'User-run backup script','SQLite snapshot + evidence; no token')],
  'edges':[('extension','bridge','Authenticated batch sync'),('bridge','store','Validated import'),('web','store','Allowlisted API operations'),('external','store','Catalog operations in local environment'),('store','backup','Explicit backup command')],
  'gap':'Local retrieval is not a promise that an external agent stays local. What an external agent sends to its provider depends on that agent; this app does not observe it.'},
 {'id':'navigation','title':'View and reader lifecycle','question':'What changes when you switch destinations?',
  'nodes':[('sources','Sources view',['D08','D21','D23'],'Browser','Cached list + query draft'),('reader','Selected source reader',['D25','D27','D57'],'Browser','Selection + previous scroll/focus'),('notes','Notes view',['D21','D37'],'Browser','Cached latest-artifact results'),('reviews','Reviews view',['D21','D22','D39'],'Browser','Cached request results'),('refresh','Explicit refresh / new query',['D18','D19','D22'],'Browser','New result ID; source selection clears')],
  'edges':[('sources','reader','Read post'),('reader','sources','Back to list: restore focus'),('sources','notes','Switch destination; retain Sources state'),('sources','reviews','Switch destination; retain Sources state'),('notes','sources','Return without new source search'),('reviews','sources','Return without new source search'),('sources','refresh','Submit or Refresh'),('refresh','sources','Latest response wins')],
  'gap':'Cached views can be stale after external work. Navigation deliberately preserves context rather than implicitly refreshing data.'},
]

# Current-state diagrams retain explicit uncertainty at real observation boundaries.
journey=next(g for g in DIAGRAMS if g['id']=='journey')
journey['nodes'][-1]=('outcome','Record next action and outcome',['D61'],'Person + local server','Source-linked action and outcome')
journey['edges'][-1]=('note','outcome','Plan an action from its source')
journey['gap']='Reasons and outcomes are authored by the person. One action is stored per captured source version; reminders are not scheduled automatically.'
reviews=next(g for g in DIAGRAMS if g['id']=='reviews')
reviews['title']='Review queue and tracked execution'
reviews['nodes']=[('choose','Choose exact source',['D38','D63'],'Person','Selected observation ID'),('pending','Queue pending review',['D39'],'Server','Media request + receipt'),('starting','Start Codex explicitly',['D40','D66'],'Person + local worker','Run ID'),('running','Codex acknowledged',['D62'],'Codex process','Heartbeat + last activity'),('blocked','Blocked / failed',['D45','D62'],'Worker','Persistent error and retry path'),('draft','Draft ready',['D40','D62'],'Codex + worker','Unpublished draft'),('complete','Inspect and save review',['D41','D42','D64'],'Person + server','Atomic evidence + completion receipt'),('stopped','Cancelled / interrupted',['D62'],'Person / heartbeat monitor','Terminal attempt; late result ignored')]
reviews['edges']=[('choose','pending','Queue selected source'),('pending','starting','Start Codex review'),('starting','running','thread.started / turn.started'),('starting','blocked','Setup failure'),('running','blocked','Observed provider failure'),('running','draft','Valid structured result + completion'),('draft','complete','User inspects and saves'),('pending','complete','Manual review'),('running','stopped','Cancel or heartbeat expiry')]
reviews['gap']='Only runs started here are observable. Audio/video cannot be inferred from a thumbnail; unsupported or insufficient evidence is reported in the draft.'
notes=next(g for g in DIAGRAMS if g['id']=='notes')
notes['nodes']=[('draft','Draft + exact citations',['D30','D31'],'Person + browser','Session storage'),('attempt','Stable save request',['D36','D64'],'Browser','Request ID + immutable submitted input'),('commit','Atomic note commit',['D32','D33'],'Server','Investigation + artifact + receipt'),('saved','Acknowledge and clear draft',['D36'],'Browser','Saved note'),('uncertain','Lost response',['D44','D46'],'Browser','Draft and request retained'),('reconcile','Look up or replay same ID',['D46','D64'],'Browser + server','One committed result')]
notes['edges']=[('draft','attempt','Save'),('attempt','commit','Validated input'),('commit','saved','Response received'),('attempt','uncertain','Connection lost or timeout'),('uncertain','reconcile','Receipt lookup; safe replay'),('reconcile','saved','Original committed result')]
notes['gap']='not_found is not proof that an in-flight write failed. An unchanged retry uses the same ID; newer edits reconcile the old submission first.'
search=next(g for g in DIAGRAMS if g['id']=='search');search['gap']='New evidence can still predate the meaning index. Activity offers a tracked rebuild. Fixture latency budgets do not establish personal-library relevance.'
nav=next(g for g in DIAGRAMS if g['id']=='navigation');nav['gap']='Polling shows committed external updates without replacing the reader. Accepting refresh preserves selection and scroll. Remote source changes still require capture.'

# Each is a proposed improvement derived from explicit current rules, not a shipped feature.
GAPS = [
 ('G01','First','An observable agent execution contract',['D39','D40','D47'],'A pending review says nothing about whether an agent ran.','Choose an actual runner/provider integration before adding running or quota-blocked badges. Define run ID, acknowledgment, heartbeat, failure payload, cancellation and reconciliation.','An injected quota error reaches the request it belongs to; UI shows blocked and a retry path without losing evidence.'),
 ('G02','First','Choose the actual review target',['D38','D28'],'The first non-post excerpt can be a linked page, quote or arbitrary attachment.','Show attachment choices, coverage and a preview; bind the request to an explicitly selected observation.','With two images and one linked page, the selected image ID is the one submitted.'),
 ('G03','First','Reconcile uncertain writes',['D32','D42','D46'],'A timeout can leave saved work plus an editable draft, with no reliable acknowledgment.','Give write actions stable request IDs and an outcome lookup; reconcile before retrying.','Lose the response after commit, retry the same operation, and retain exactly one intended save.'),
 ('G04','Next','Set search quality and latency budgets',['D11','D12','D17','D60'],'Warm microbenchmarks do not answer whether the first query feels fast or results are useful.','Create a labelled query set and measure cold/warm end-to-end p50/p95, recall of expected sources and time to first useful result. Budgets remain a product decision.','A repeatable benchmark reports separate cold and warm timings plus expected-source retrieval; no fabricated target is called an existing promise.'),
 ('G05','Next','Make coverage and freshness actionable',['D12','D16','D28','D41'],'Labels exist, but missing extraction and stale meaning evidence do not have one clear repair workflow.','Offer per-source coverage and index freshness with explicit fetch, inspect, transcribe or rebuild actions and their costs.','A new transcript immediately matches words; UI explains why meaning search has not caught up and offers a verified rebuild path.'),
 ('G06','Next','Show external changes without losing context',['D21','D22'],'A completed external review can remain visually pending in a cached view.','Use revision-aware refresh or an update notice; preserve selected source and reading position.','An external completion produces an update notice, and accepting it retains reading context.'),
 ('G07','Later','Connect saves to outcomes',['D31','D37','D59'],'The app retrieves and records findings, but does not track what the person eventually did with a save.','Define optional reason, intended action and completion evidence, without treating inferred categories as personal intent.','A person can record and later find a finished action linked to the original saved source.'),
 ('G08','Next','Close accessibility and visual-test gaps',['D27','D56','D57'],'DOM controller tests do not establish real keyboard, contrast or responsive usability.','Add browser acceptance for focus, announcements, dialogs, 320px layouts and both Scan/Read paths; record remaining manual checks.','A keyboard-only user can inspect, cite and recover from a failure without losing focus or encountering horizontal page overflow.'),
]

SCENARIOS = [
 ('S01','The agent has no usage left',['D39','D40','D45'],['Request is saved as pending','External agent stops outside the app','No run/usage event reaches this app','UI can truthfully say waiting / external status unknown'],'A running or failed badge would be invented. G01 supplies the missing observation contract.'),
 ('S02','The save succeeds but its response is lost',['D32','D44','D46'],['Save request reaches server','Artifact commits','Browser receives no acknowledgment','Timeout restores the draft; saved note may exist'],'Refresh and reconcile before retry. G03 makes the outcome queryable.'),
 ('S03','A new transcript is missing from meaning results',['D10','D12','D41'],['Review completion stores derived text','Word index invalidates','Existing meaning index stays pinned','Words can match while meaning cannot yet match'],'Rebuild meaning evidence explicitly; do not describe the older index as current.'),
 ('S04','An old query finishes after a new query',['D18','D19'],['Query A starts','Query B gets a newer generation','B renders first','A returns with an obsolete generation'],'Ignore A in the UI. Its server work is not necessarily cancelled.'),
 ('S05','A post contains several attachments',['D28','D38'],['Result contains several supporting passages','Request media review chooses first non-post passage','No target picker is shown','Request is bound to the selected observation ID'],'Current selection can differ from intent. G02 requires an explicit choice.'),
 ('S06','Hybrid search cannot read its model',['D16','D45'],['User submits Words + meaning','Meaning index or runtime fails','Known failure is caught','Word results show fallback notice'],'Semantic-only should surface an error; hybrid must label the fallback.'),
 ('S07','A worker processes only part of a job',['D48','D49','D50'],['Worker acquires lease','Each item checkpoints results or error','Batch bound is reached','Job returns to pending if items remain'],'A caller must run another batch; pending is not proof of an active scheduler.'),
 ('S08','A saved citation changes remotely',['D06','D33','D37'],['A claim pins an immutable captured span','Remote author changes their post','No recapture happens yet','The old captured citation remains valid as a quote'],'Remote changes are unknown until captured. Staleness flags compare captured versions.'),
]


DELIVERED = {
 'G01':('Local Codex runner with persistent acknowledgment, heartbeat, quota/configuration errors, cancellation and drafts.','Installed and signed-in Codex is required. Work launched elsewhere remains unobserved.'),
 'G02':('Explicit source picker, captured previews and per-attachment extraction actions.','Remote access and optional extraction dependencies can fail.'),
 'G03':('Atomic note/review commits and durable request receipts; UI reconciles and safely replays uncertain writes.','Legacy direct artifact operations still use version checks without the new UI receipts.'),
 'G04':('Fresh-process and warm HTTP benchmark with labelled fixtures, p50/p95, hit@5 and configurable budgets.','Personal-library relevance and semantic timing require separate labelled evaluation; fixture results are not a universal claim.'),
 'G05':('Coverage picker, capture workers, index revision status and tracked rebuild with progress.','No built-in audio transcription. Old indexes without receipt sidecars report unknown freshness until rebuilt.'),
 'G06':('Five-second token polling and explicit update notices; accepted refresh retains the selected source and scroll.','There can be polling delay; remote source changes are unknown until captured.'),
 'G07':('Actions destination with reason, next action, optional due date and required completion outcome.','One action per captured observation; no recurring reminders or scheduling.'),
 'G08':('Real browser acceptance for keyboard focus, workflow recovery and 320px layouts.','Full screen-reader and all-device accessibility audit remains manual.'),
}


def reference(path, anchor):
    lines = (ROOT / path).read_text(encoding='utf-8').splitlines()
    found = [i + 1 for i, line in enumerate(lines) if anchor in line]
    if not found:
        raise ValueError(f'Missing anchor: {path}: {anchor}')
    return {'path':path, 'line':found[0], 'anchor':anchor}


def build_data():
    decisions = []
    for ident, area, title, rule, consequence, acceptance, file, anchor in RULES:
        decisions.append(dict(id=ident, area=area, title=title, status='Implemented', rule=rule,
            consequence=consequence, acceptance=acceptance, source=reference(file,anchor),
            test=reference(*TESTS[ident]) if ident in TESTS else None,
            rationale='Historical rationale not established by this audit; consequence is analysis of the current behavior.'))
    diagrams = []
    ids = {d['id'] for d in decisions}
    for raw in DIAGRAMS:
        nodes = [dict(id=i,label=l,decisions=ds,owner=o,persisted=p,status='Unknown' if i in ('unknown','uncertain') else 'Implemented' if ds else 'Proposed') for i,l,ds,o,p in raw['nodes']]
        node_ids = {n['id'] for n in nodes}
        for n in nodes:
            assert set(n['decisions']) <= ids
        edges = [dict(source=a,target=b,label=c) for a,b,c in raw['edges']]
        assert all(e['source'] in node_ids and e['target'] in node_ids for e in edges)
        diagrams.append({**raw,'nodes':nodes,'edges':edges})
    operations = []
    for op in catalog():
        method = getattr(Workspace, op['name'])
        operations.append({'name':op['name'],'description':op['description'],
            'web':op['name'] in ALLOWED, 'parameters':op['inputSchema'],
            'source':{'path':pathlib.Path(inspect.getsourcefile(method)).relative_to(ROOT).as_posix(),
                      'line':inspect.getsourcelines(method)[1],'anchor':'def '+op['name']}})
    controls = []
    import re
    for match in re.finditer(r'<(button|input|select|textarea|a)\b[^>]*>',(ROOT/HTML).read_text(encoding='utf-8')):
        tag = match[0]; ident = re.search(r'\bid="([^"]+)"',tag)
        if ident: controls.append({'id':ident[1],'element':match[1],'source':reference(HTML,'id="'+ident[1]+'"')})
    paths = {d['source']['path'] for d in decisions} | {o['source']['path'] for o in operations} | {HTML,'docs/ui-design.md'}
    paths |= {d['test']['path'] for d in decisions if d['test']}
    fingerprints = {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(paths)}
    gaps = [dict(id=i,priority=p,title=t,decisions=ds,problem=problem,proposal=DELIVERED[i][0],remaining=DELIVERED[i][1],acceptance=a,status='Implemented') for i,p,t,ds,problem,proposal,a in GAPS]
    scenarios = [dict(id=i,title=t,decisions=ds,steps=steps,conclusion=c) for i,t,ds,steps,c in SCENARIOS]
    scenarios[0].update(steps=['Queue the selected source','Start Codex review explicitly','Provider returns a usage error','Worker persists blocked status and retry guidance'],conclusion='Runs started here are observable; external agent sessions remain outside this app.')
    scenarios[1].update(steps=['Submit note with stable request ID','Server atomically commits note and receipt','Response is lost','UI looks up receipt or replays the same ID'],conclusion='The original save is recovered; identical retries do not duplicate the note.')
    scenarios[4].update(steps=['Open source coverage','Inspect all attachment options and previews','Select attachment B explicitly','Queue its observation ID'],conclusion='No attachment is selected automatically. Uncaptured attachments must be captured first.')
    for item in gaps+scenarios: assert set(item['decisions']) <= ids
    return dict(title='Inside the inator', date='2026-09-24', decisions=decisions, diagrams=diagrams,
        gaps=gaps, scenarios=scenarios, operations=operations, controls=controls, fingerprints=fingerprints,
        scope='Sources/Notes UI plus its capture, evidence, job and storage boundaries. Code inspection with linked regression tests; not a claim that every behavior has been browser-tested or that every historical design rationale is known.',
        omissions=['No personal library content or credentials included.', 'Remote agent implementation and provider behavior are outside this checkout.',
                   'Exact style declarations remain in CSS; historical reasons for individual values are not reconstructed.',
                   'Static control inventory excludes dynamically generated per-result controls; those are covered by flow decisions, not mechanically enumerated.',
                   'Acceptance examples without a linked test are proposed checks, not passed tests. Linked tests may cover only part of a decision.'])


def markdown(data):
    out = ['# Inside the inator — visual specification','',data['scope'],'',
        'Generated from `scripts/build_visual_spec.py`. Regenerate with `python scripts/build_visual_spec.py`; detect drift with `python scripts/build_visual_spec.py --check`. The interactive companion is [visual-spec.html](visual-spec.html).',
        '', 'Implemented = observed in code. Proposed = not shipped. Unknown = missing observation or rationale. A linked test is relevant coverage, not proof of the entire rule.','', '## System maps','']
    for g in data['diagrams']:
        out += ['### '+g['title'],'',g['question'],'','```mermaid','flowchart TD']
        for n in g['nodes']: out.append(f'  {n["id"]}["{n["label"]}"]')
        for e in g['edges']: out.append(f'  {e["source"]} -->|"{e["label"]}"| {e["target"]}')
        out += ['```','', '**Gap:** '+g['gap'],'']
        for n in g['nodes']: out.append(f'- **{n["label"]}** — owner: {n["owner"]}; retained state: {n["persisted"]}; decisions: '+', '.join(n['decisions']))
        out.append('')
    out += ['## Decision register','']
    for d in data['decisions']:
        s=d['source']; out += [f'### {d["id"]} · {d["title"]}','',d['rule'],'', '**Consequence:** '+d['consequence'],'','**Acceptance example:** '+d['acceptance'],'',f'**Code:** [{s["path"]}:{s["line"]}](../{s["path"]}#L{s["line"]})']
        if d['test']:
            t=d['test'];out.append(f'**Related test:** [{t["anchor"]}](../{t["path"]}#L{t["line"]})')
        else: out.append('**Verification:** code inspection; no specific automated test mapped in this register.')
        out += ['',d['rationale'],'']
    out += ['## Improvement implementation status','']
    for g in data['gaps']:
        out += ['### '+g['id']+' · '+g['title']+' ('+g['priority']+')','',g['problem'],'',g['proposal'],'','**Remaining limits:** '+g['remaining'],'','**Acceptance:** '+g['acceptance'],'','**Derived from:** '+', '.join(g['decisions']),'']
    out += ['## Acceptance walkthroughs','']
    for s in data['scenarios']:
        out += ['### '+s['id']+' · '+s['title'],'']+[f'{i+1}. {x}' for i,x in enumerate(s['steps'])]+['',s['conclusion'],'']
    out += ['## Catalog boundary','',f'All {len(data["operations"])} catalog operations are enumerated in visual-spec.json and the interactive API view; {sum(o["web"] for o in data["operations"])} are web-allowlisted. Web-allowlisted does not mean a dedicated UI control exists.','', '## Limits of this specification','']+['- '+x for x in data['omissions']]
    return '\n'.join(out)+'\n'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    data=build_data()
    payload=json.dumps(data,ensure_ascii=False,indent=2)
    template=(ROOT/'docs/visual-spec.template.html').read_text(encoding='utf-8')
    document=template.replace('__SPEC_DATA__',payload.replace('<','\\u003c'))
    outputs={'docs/visual-spec.json':payload+'\n','docs/visual-spec.md':markdown(data),'docs/visual-spec.html':document}
    for name,content in outputs.items():
        path=ROOT/name
        if args.check:
            if not path.exists() or path.read_text(encoding='utf-8')!=content:raise SystemExit('Stale visual specification: '+name)
        else:path.write_text(content,encoding='utf-8')
    print(f'{"Checked" if args.check else "Built"}: {len(data["diagrams"])} maps, {len(data["decisions"])} decisions, {len(data["operations"])} operations, {len(data["scenarios"])} scenarios; source anchors and output freshness valid.')

if __name__=='__main__':main()
