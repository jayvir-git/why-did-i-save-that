# Validation

Run `python -m unittest discover -s tests -p "test_*.py"` and `node --test tests/*.test.cjs`, then `node scripts/check.cjs`, `node scripts/build.cjs --check`, and `node --check gold_workspace/web/app.js`.

Tests cover immutable snapshots, import idempotency, source spans, read-only SQL, jobs, fake semantic embeddings, shared attachment parents, quoted evidence, full-document passage coverage, research version staleness, media completion, hybrid fallback, and the web app's origin/path restrictions. Extension tests cover normalization, network observation, startup isolation, review behavior, video metadata and authenticated sync.

Tests are synthetic regression checks, not a benchmark proving retrieval quality on arbitrary libraries. Actual X availability and network response shapes can change. For acceptance, import your own backup, compare counts, search known phrases in post and attachment text, inspect exact quotes, save and resume research, complete one media request, restart the app and verify persistence. Run doctor.py to check optional runtime assets. Keep real-library acceptance reports and all captured data private.

## Workspace interface

`tests/workspace-ui.test.cjs` runs the real UI controller with a small DOM adapter and recorded API calls. It checks cached navigation, in-flight and stale searches, query drafts, pagination, Scan/Read continuity, reader selection, browse startup, and direct destination links/browser Back. It does not simulate CSS layout or replace visual browser checks. Python tests verify stable browse snapshots and exact evidence spans without invoking semantic search.

Run `python scripts/preview_ui.py`, then visit `http://127.0.0.1:8770` for the real interface backed by 24 synthetic posts. Stop with Ctrl+C to clean up the temporary workspace. Use this preview for note saves and review completion without changing a personal archive.

Check Sources, Notes, and Review queue at desktop and narrow mobile widths. Open and close the reader; verify list position and selected source survive navigation. Exercise Load more, keyword search, Browse all, empty results, and missing semantic-model recovery. Check note draft recovery after reload, citation removal, and saving. Confirm visible keyboard focus, dialog Escape behavior, browser Back, and no horizontal overflow at 320px. Design and interaction rules are in [docs/ui-design.md](docs/ui-design.md).


Search regression tests cover reuse across HTTP-style connections, invalidation after imports and review completion, semantic cache reuse and pinned-index behavior. UI tests cover stalled requests, usage errors, network failures, malformed responses, button recovery, draft retention, and explicit waiting states for reviews. Run the attachment tests with NumPy installed to exercise matrix scoring; the same tests also cover the dependency-free fallback in a Python environment without NumPy.


## Visual specification

`python scripts/build_visual_spec.py --check` checks source/test anchors, graph references, catalog enumeration and generated-file freshness. Regenerate with `python scripts/build_visual_spec.py` after reviewing affected decisions. The source register is in that script; the display template is `docs/visual-spec.template.html`.

With Playwright available, `node scripts/check_visual_spec.cjs` checks every map and node, decision search, walkthrough stepping, API filtering, 360px overflow and browser errors in the generated offline artifact. It launches installed Edge headlessly. This checks the specification viewer, not the product's accessibility or end-to-end behavior.


## Workflow and search acceptance

`python -m unittest discover -s tests -p "test_workflows.py"` covers concurrent/idempotent writes, invalid-citation rollback, atomic review replay, explicit attachment coverage, target validation, worker deduplication, cancellation, stale heartbeat, Codex JSONL drafts, persisted quota errors and action version conflicts. Provider-event fixtures do not spend usage.

`node scripts/check_workflows.cjs` uses Playwright and installed Edge against a disposable 24-post workspace. It verifies the real target picker, visible quota recovery, a committed save whose HTTP response is dropped, next-action/outcome editing, external updates without losing the reader, focus return and 320px layouts. No personal archive or live provider is used.

`python scripts/benchmark_search.py --output docs/search-benchmark.json` measures HTTP search plus the first page against 1,200 synthetic posts and six labelled queries. Fresh server processes supply cold samples; warm samples reuse a server. Initial fixture regression budgets are cold p95 <= 2,500 ms, warm p95 <= 500 ms and expected-source hit@5 = 1.0. Override budgets explicitly for other machines. OS disk cache is not flushed and browser painting is excluded. `--mode hybrid` or `semantic` requires a working local model, builds a fixture index and rejects fallback as a benchmark success. Personal-library relevance still needs user-labelled examples; synthetic scores do not establish it.

One live installed-CLI smoke test using only a synthetic sentence reached a review draft on 2026-09-24 with normal user-profile access. Running the CLI inside a filesystem-restricted test sandbox produced configuration/permission failures, which were surfaced rather than hidden. Automated browser and event-fixture checks remain repeatable without spending account usage.


## Agent onboarding and providers

`python scripts/demo.py` checks synthetic import, keyword retrieval, an exact cited note, idempotent replay, persistence across processes, and MCP initialize/list/call. Its archive is disposable. `python scripts/check_fresh_install.py` runs setup twice in a clean source copy without runtime/model/private files, from a different working directory, then launches the generated MCP command. Both are offline and spend no provider usage; baseline fresh-install checks run in the Windows/Linux CI matrix.

`tests/test_setup.py` checks configuration merge/replay and conflict preservation. `tests/test_providers.py` checks provider persistence, legacy defaults, cross-provider deduplication, Claude selected-text/image inputs, tool restrictions, structured success, malformed results, missing completion, timeouts and quota recovery. UI tests check selection and retry routing. These fixtures do not claim a live Claude session passed. Optional model downloads/package installs are not part of the clean offline acceptance check.
