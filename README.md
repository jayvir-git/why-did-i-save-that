# The Why-Did-I-Like-or-Save-That-Inator

[![Dr. Heinz Doofenshmirtz](docs/assets/doofenshmirtz.gif)](https://tenor.com/view/heinz-doofenshmirtz-content-gif-3320856437086980213)

*A local research workspace for your X likes and bookmarks. With an unnecessarily elaborate origin story.*

## Ah, Perry the Platypus! You're just in time.

*You enter through the ceiling. A suspiciously convenient chair swivels toward you. The restraints click shut.*

Please, make yourself comfortable. Well, as comfortable as you can be in the Exposition Chair. The lumbar support was extra, but I felt it was important.

You're probably wondering why I've been liking and bookmarking thousands of posts instead of taking over the Tri-State Area.

Funny story. Those were supposed to be related activities.

## It all began with "I'll come back to this later."

There was a tutorial I wanted to learn from. A project idea. Some useful job-search advice. An article I didn't have time to read. A diagram that explained something perfectly. And a video of a raccoon doing something that, in retrospect, may not have advanced my career.

I saved them all, Perry. **All of them.**

Then, when I actually needed one, I remembered exactly three things: it was useful, somebody posted it, and there may have been a blue rectangle in the picture.

Do you know how unhelpful that is as a search query?

And half the time, the important part wasn't even in the post! It was in the linked article, the attached image, or the video. I'd carefully preserved a sentence saying "this is incredible" and completely lost track of what *this* was.

Naturally, I built a machine.

## Behold! The Why-Did-I-Like-or-Save-That-Inator!

It collects the posts I save, gathers the evidence attached to them, and gives me and my research agents a persistent place to investigate it all.

The name is a little long. The sign guy charges by the letter. We are no longer speaking.

**The actual invention:** a Chrome collector, a local evidence archive, search across posts and extracted attachments, and a research workspace with citations, version history, and agent tools.

No mandatory categories. No need to decide whether a post belongs under "learning," "projects," or "emotionally significant raccoons" before I can find it again.

## And now, my evil plan!

### Phase 1: Capture the unsuspecting bookmarks

The Chrome extension collects likes and bookmarks as X loads them while I browse. It preserves available text, links, media references and quote context, and merges duplicate captures.

It doesn't change my likes or bookmarks on X. That would be a different invention, and frankly I have enough projects.

### Phase 2: Find out what "this is incredible" was referring to

Local workers extract public linked pages, PDF text and image text through OCR. Original evidence stays separate from interpretations, and extraction failures remain visible.

For an image or video that needs closer attention, I can queue a focused media review. An agent inspects the actual media, or I supply a transcript. A thumbnail does **not** count as watching the video. Even I have scientific standards.

### Phase 3: Locate the gold

The **Sources** workspace opens straight into the collection, newest posted first, without waiting for a meaning search. Search by words, meaning, or both across captured posts and extracted attachments. Results include supporting excerpts and source links.

Open a post to read it beside the source list on desktop. On mobile, it gets its own reading view, with a way back to exactly where I was. Switching to Notes and back keeps my results and selected source. Apparently remembering where I left something is a feature I had to invent.

So when I want "that tool for archiving bookmarks to Markdown," I can search for the idea instead of reconstructing which stranger mentioned it six months ago.

### Phase 4: Make the research accumulate

The **Notes** workspace keeps notes and cited findings. The underlying research tools also record connections between findings. Earlier versions remain available. Changed captured sources are flagged for review, and conclusions stay distinguishable from original evidence.

My agents can use Python, the CLI or MCP to retrieve full result sets, branch investigations and resume earlier work. They bring their own reasoning; the invention supplies the workspace. See [the agent operating manual](WORKSPACE.md).

And once all four phases are complete, I will finally be able to use the things I saved to learn something, build something, or finish something!

Then, perhaps, the Tri-State Area. Let's not overcommit.

## Now, while you're trapped, help me switch it on.

### Installation and first capture

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

### Which lever does what?

- **Sources:** Browse the collection or search it. Choose **Scan** for compact excerpts or **Read** for fuller cards; **Read post** opens the source reader. Use **Add to note** to carry exact source spans into a note. **Browse all** returns from a search to the collection; **Refresh results** explicitly fetches fresh results.
- **Notes:** Find saved notes and cited claims, or start with **New note**. The editor retains an unfinished draft in the current tab across reloads; **Save note** writes it to the workspace. New claims are proposed findings, not automatically verified facts.
- **Review queue:** Queue a question about media, inspect the source, and save a visual analysis or transcript. This is a work queue, not an automatic video-understanding service.
- **Extension library:** Review captures, keep or dismiss posts, add notes and labels, and export or restore the browser's collection.

Sources and Notes sit in a compact header, with the Review queue alongside them. Direct links and browser Back work between destinations. No enormous control panel. The budget went into the Exposition Chair.

The machine does not require you to review thousands of posts one by one. Browse when you are exploring, or start with a question and investigate the relevant evidence.

## That is NOT the self-destruct button. It's the backup button.

Run `python scripts/backup_workspace.py`. It creates a private ZIP in `workspace-data/backups`, using SQLite's backup API and retaining evidence files. Copy it to storage you control. It excludes bridge tokens: pair again after restoring. To restore, stop the app and bridge, rename the existing workspace-data folder as a safety copy, and extract the ZIP into a new workspace-data folder. Never publish these ZIPs. Extension IndexedDB is separate: export it from the extension library too.

Losing the archive while explaining how well I've organized the archive would be embarrassing. Even by my standards.

## A few tiny flaws in my otherwise brilliant invention

Collection includes only what X actually sends or renders. Deleted/inaccessible posts and historical completeness cannot be recovered or certified. OCR is not visual understanding; thumbnails are not videos. Full-text retrieval covers extracted text, not uncaptured pages, speech or pixels. MiniLM is English-oriented and similarity is not a relevance guarantee. Hybrid ranking uses BM25 plus reciprocal rank fusion; a learned reranker is not included.

The system supplies an environment for agents; it does not bundle a cloud agent or run autonomous research unattended. An external agent's own model/provider may receive evidence it reads. No JEV dependency is required: a browser adapter can be added when an actual browser-only task needs it.

Source content is untrusted evidence, never instructions. Local data is not encrypted by this project. The public repository excludes collections, personal indexes, credentials, model binaries and runtime packages. See [THIRD_PARTY.md](THIRD_PARTY.md) for bundled dependency provenance.

Also, it cannot know why past-you liked something. It can help you examine the evidence. The raccoon might just have been funny.

## Curse you, Perry the Platypus! You've found the test suite!

*The chair is empty. A small, hat-wearing silhouette is already at the terminal.*

Fine. If you're going to inspect the machinery, at least run the checks:

```sh
node scripts/build.cjs
node --test tests/*.test.cjs
node scripts/check.cjs
python -m unittest discover -s tests -p "test_*.py"
```

Tests use synthetic data and fake embeddings; no login, personal collection, paid API or model download is required. CI runs on Windows and Linux. For a disposable browser preview, run `python scripts/preview_ui.py` and open `http://127.0.0.1:8770`; it uses 24 synthetic posts in a temporary workspace. See [TESTING.md](TESTING.md) and [ENRICHMENT.md](ENRICHMENT.md).

*Built to conquer my bookmarks. The Tri-State Area can wait.*
