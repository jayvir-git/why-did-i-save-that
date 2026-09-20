# Validation

Run `python -m unittest discover -s tests -p "test_*.py"` and `node --test tests/*.test.cjs`, then `node scripts/check.cjs`, `node scripts/build.cjs --check`, and `node --check gold_workspace/web/app.js`.

Tests cover immutable snapshots, import idempotency, source spans, read-only SQL, jobs, fake semantic embeddings, shared attachment parents, quoted evidence, full-document passage coverage, research version staleness, media completion, hybrid fallback, and the web app's origin/path restrictions. Extension tests cover normalization, network observation, startup isolation, review behavior, video metadata and authenticated sync.

Tests are synthetic regression checks, not a benchmark proving retrieval quality on arbitrary libraries. Actual X availability and network response shapes can change. For acceptance, import your own backup, compare counts, search known phrases in post and attachment text, inspect exact quotes, save and resume research, complete one media request, restart the app and verify persistence. Run doctor.py to check optional runtime assets. Keep real-library acceptance reports and all captured data private.
