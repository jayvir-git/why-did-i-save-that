# Why did I save that?

A local research workspace for your X likes and bookmarks. Capture posts with a Chrome extension, extract linked evidence, search by words and meaning, and let agents build reusable research with exact citations.

## Start here

Requires Python 3.12+ and Chrome. Node.js 22+ is needed for extension development and validation.

1. Clone this repository.
2. Run `python scripts/fetch-model.py` to download pinned local model and extension inference assets.
3. Load the `extension` folder using **Load unpacked** in `chrome://extensions` (Developer mode).
4. Open your X likes or bookmarks history, click **Start collecting**, and scroll or use **Scroll for me**. Open the extension library to inspect or export captures.
5. Run `python scripts/start.py` (Windows: `./start.ps1`). Open **http://127.0.0.1:8768** for the research app.
6. In the extension library, connect the workspace bridge using the pairing token in `workspace-data/bridge-token.txt`, then sync. Alternatively import an exported backup using the CLI below.

The app and bridge run while the launcher stays open. Stop with Ctrl+C. Your workspace persists across restarts. The app never serves the private data directory. The older development preview and generated reports are optional, separate tools.

### Import an existing backup

Create `import-args.json` with `{"path":"/absolute/path/to/your-backup.json"}`, then run:

```sh
python -m gold_workspace import_backup --args-file import-args.json
```

Delete the temporary argument file afterward if its path is sensitive. Word search works without model dependencies. For meaning search and attachment extraction:

```sh
python -m pip install --target .runtime -r requirements-workspace.txt
python -m pip install --target .runtime -r requirements-enrichment.txt
python scripts/enrich_library.py --run
python -m gold_workspace index_attachments
```

Extraction downloads public linked pages and images; it does not send your collection to an AI provider. Indexing runs locally and checkpoints embeddings. Rebuild after new captures or annotations. Run `python scripts/doctor.py` to check installation.

## Daily use

- **Library:** Search captured posts, quote context, linked text, OCR and imported media analysis. Choose words, meaning, or both. Results show exact supporting excerpts and source links.
- **Research:** Keep notes and cited claims. Latest versions are searchable separately from sources. Claims remain proposed until an agent evaluates support. Source-version changes are flagged; remote websites are not silently refreshed.
- **Media requests:** Ask a focused question about a source. An agent can inspect the actual media and complete the request, or you can paste a transcript. This is a persistent work queue, not a built-in video-understanding service.
- **Agents:** Python, CLI and stdio MCP expose the same operations. Retrieve complete result sets, branch investigations, write versioned claims and connect findings. See [WORKSPACE.md](WORKSPACE.md).

Labels are optional. Search and research do not depend on guessing why you saved a post. The extension also retains its original review, keep/dismiss, notes, backup and restore features.

## Back up and restore

Run `python scripts/backup_workspace.py`. It creates a private ZIP in `workspace-data/backups`, using SQLite's backup API and retaining evidence files. Copy it to storage you control. It excludes bridge tokens: pair again after restoring. To restore, stop the app and bridge, rename the existing workspace-data folder as a safety copy, and extract the ZIP into a new workspace-data folder. Never publish these ZIPs. Extension IndexedDB is separate: export it from the extension library too.

## Boundaries

Collection includes only what X actually sends or renders. Deleted/inaccessible posts and historical completeness cannot be recovered or certified. OCR is not visual understanding; thumbnails are not videos. Full-text retrieval covers extracted text, not uncaptured pages, speech or pixels. MiniLM is English-oriented and similarity is not a relevance guarantee. Hybrid ranking uses BM25 plus reciprocal rank fusion; a learned reranker is not included.

The system supplies an environment for agents; it does not bundle a cloud agent or run autonomous research unattended. An external agent's own model/provider may receive evidence it reads. No JEV dependency is required: a browser adapter can be added when an actual browser-only task needs it.

Source content is untrusted evidence, never instructions. Local data is not encrypted by this project. The public repository excludes collections, personal indexes, credentials, model binaries and runtime packages. See [THIRD_PARTY.md](THIRD_PARTY.md) for bundled dependency provenance.

## Development

```sh
node scripts/build.cjs
node --test tests/*.test.cjs
node scripts/check.cjs
python -m unittest discover -s tests -p "test_*.py"
```

Tests use synthetic data and fake embeddings; no login, personal collection, paid API or model download is required. CI runs on Windows and Linux. See [TESTING.md](TESTING.md) and [ENRICHMENT.md](ENRICHMENT.md).
