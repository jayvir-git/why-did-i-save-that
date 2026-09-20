# Validation

Run `python -m unittest discover -s tests -p "test_*.py"` and `node --test tests/*.test.cjs`, then `node scripts/check.cjs`, `node scripts/build.cjs --check`, and `node --check gold_workspace/web/app.js`.

Tests cover immutable snapshots, import idempotency, source spans, read-only SQL, jobs, fake semantic embeddings, shared attachment parents, quoted evidence, full-document passage coverage, research version staleness, media completion, hybrid fallback, and the web app's origin/path restrictions. Extension tests cover normalization, network observation, startup isolation, review behavior, video metadata and authenticated sync.

Tests are synthetic regression checks, not a benchmark proving retrieval quality on arbitrary libraries. Actual X availability and network response shapes can change. For acceptance, import your own backup, compare counts, search known phrases in post and attachment text, inspect exact quotes, save and resume research, complete one media request, restart the app and verify persistence. Run doctor.py to check optional runtime assets. Keep real-library acceptance reports and all captured data private.

## Workspace interface

`tests/workspace-ui.test.cjs` runs the real UI controller with a small DOM adapter and recorded API calls. It checks cached navigation, in-flight and stale searches, query drafts, pagination, Scan/Read continuity, reader selection, browse startup, and direct destination links/browser Back. It does not simulate CSS layout or replace visual browser checks. Python tests verify stable browse snapshots and exact evidence spans without invoking semantic search.

Run `python scripts/preview_ui.py`, then visit `http://127.0.0.1:8770` for the real interface backed by 24 synthetic posts. Stop with Ctrl+C to clean up the temporary workspace. Use this preview for note saves and review completion without changing a personal archive.

Check Sources, Notes, and Review queue at desktop and narrow mobile widths. Open and close the reader; verify list position and selected source survive navigation. Exercise Load more, keyword search, Browse all, empty results, and missing semantic-model recovery. Check note draft recovery after reload, citation removal, and saving. Confirm visible keyboard focus, dialog Escape behavior, browser Back, and no horizontal overflow at 320px. Design and interaction rules are in [docs/ui-design.md](docs/ui-design.md).
