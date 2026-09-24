# The Why-Did-I-Like-or-Save-That-Inator

[![Dr. Heinz Doofenshmirtz](docs/assets/doofenshmirtz.gif)](https://tenor.com/view/heinz-doofenshmirtz-content-gif-3320856437086980213)

A local research workspace for your X likes and bookmarks. Capture posts, search their text and extracted attachments, and turn useful sources into cited notes and actions.

*Built to conquer my bookmarks. The Tri-State Area can wait.*

[Quick start](#quick-start) · [Features](#features) · [Usage](#usage) · [Optional capabilities](#optional-capabilities) · [Privacy and limitations](#privacy-and-limitations) · [Backup and restore](#backup-and-restore) · [Development](#development) · [Visual specification](#visual-specification)

## Quick start

Requires **Python 3.12+**. Collecting new posts also requires **Chrome**. Run commands from the repository directory. Node.js 22+ is needed only for extension development and validation.

```sh
git clone https://github.com/jayvir-git/why-did-i-save-that.git
cd why-did-i-save-that
python scripts/start.py
```

Open [the local app](http://127.0.0.1:8768). On Windows, you can use `./start.ps1` instead of the Python launcher. The app and capture bridge run while the launcher stays open; stop with Ctrl+C. Your workspace persists across restarts.

**Next:** collect posts with the extension or import an existing backup below. Browsing, word search and notes work without model dependencies or an AI account.

### Collect posts with Chrome

1. Run `python scripts/fetch-model.py` to download the pinned local model and extension inference assets.
2. Open `chrome://extensions`, enable **Developer mode**, choose **Load unpacked**, and select this repository's `extension` folder.
3. Open your X likes or bookmarks history, click **Start collecting**, and scroll or use **Scroll for me**. Open the extension library to inspect or export captures.
4. With the local app running, connect the extension library to the workspace bridge using the pairing token in `workspace-data/bridge-token.txt`, then sync.

Collection preserves available text, links, media references and quote context, merging duplicate captures. It does not change your likes or bookmarks on X.

### Import an existing backup

For an exported extension backup, create `import-args.json` containing:

```json
{"path":"/absolute/path/to/your-backup.json"}
```

Then run:

```sh
python -m gold_workspace import_backup --args-file import-args.json
```

On Windows, use forward slashes in the JSON path, such as `C:/Users/you/Downloads/backup.json`. Remove the temporary argument file afterward if its path is sensitive. To restore a full workspace ZIP, see [Backup and restore](#backup-and-restore).

## Features

- **Search your collection:** Browse posts immediately or search by words. Optional local meaning search finds related ideas across posts and extracted attachments, with supporting excerpts and source links.
- **Keep evidence traceable:** Preserve original captures separately from OCR, interpretations and cited findings. Research tools retain earlier versions and flag changed captured sources.
- **Build useful notes:** Save notes with exact source spans. Interrupted saves can be reconciled without creating duplicates.
- **Follow through:** Record why a source matters, a next action, an optional due date and a completion outcome.
- **Review selected evidence:** Choose the source or attachment explicitly. Tracked Codex reviews show progress, usage failures and drafts for you to inspect before saving.

No mandatory categorization or one-by-one review of your entire collection is required.

## Usage

- **Sources:** Choose **Scan** for compact excerpts or **Read** for fuller cards. **Read post** opens a source beside the list on desktop or in a dedicated mobile view. **Add to note** carries exact source spans into a note. **Browse all** returns to the collection. Attachment selection shows what has been captured and offers extraction when available.
- **Notes:** Find saved notes and cited findings, or select **New note**. An unfinished note draft survives reloads in the current tab; **Save note** writes it to the workspace. Proposed findings are not automatically verified facts.
- **Actions:** Use **Plan an action** on a source to record a reason and next step. Complete it by recording an outcome.
- **Review queue:** Inspect a requested source and enter your own analysis or transcript, or explicitly start a [Codex review](#codex-reviews). **Open review editor** brings the ready draft and its limitations into view, fills an empty editor and preserves existing edits. Inspect the result, then choose **Save review** to make it searchable evidence.
- **Activity & evidence freshness:** Check tracked work, cancel or retry tasks, and rebuild the meaning index. External changes produce an update notice; accepting a refresh preserves your selected source and reading position.
- **Extension library:** Inspect captures, keep or dismiss posts, add notes and labels, and export or restore the browser's collection.

Switching between Sources and Notes preserves results and the selected source. Direct destination links and browser Back are supported.

## Optional capabilities

### Local meaning search

Download the model assets if you have not already, install the search dependencies, then build an index:

```sh
python scripts/fetch-model.py
python -m pip install --target .runtime -r requirements-workspace.txt
python -m gold_workspace index_attachments
```

Choose meaning search or words + meaning in Sources. Indexing runs locally and checkpoints embeddings. Rebuild after new captures or annotations, using the command above or **Rebuild meaning index** in Activity.

### Attachment extraction

Install the extraction dependencies and capture public linked pages, PDF text and image text through OCR:

```sh
python -m pip install --target .runtime -r requirements-enrichment.txt
python scripts/enrich_library.py --run
```

You can also request capture for a specific referenced attachment in the app. Rebuild the meaning index afterward to include new evidence. Extraction downloads public pages and images; it does not send your collection to an AI provider. Failures and incomplete coverage remain visible. Run `python scripts/doctor.py` to check installation; see [ENRICHMENT.md](ENRICHMENT.md) for details.

### Codex reviews

Requires an installed, signed-in Codex CLI. From a pending review, choose **Start Codex review**. The selected captured text or supported cached image and your question are sent to your signed-in provider and use your account allowance. Progress, configuration errors and usage-limit failures appear in the app.

A successful response remains a draft until you inspect and save it. Full audio/video transcription is not included; a thumbnail does not establish what happens in a video.

### Agent tools

Python, CLI and MCP interfaces let agents retrieve full result sets, branch investigations and resume earlier work. See [WORKSPACE.md](WORKSPACE.md) for the operation catalog and setup. Agents bring their own reasoning and provider; evidence they read may be sent to that provider.

## Privacy and limitations

- **Local storage:** The app stores its workspace locally and does not serve the private data directory. This project does not encrypt local data. The public repository excludes collections, personal indexes, credentials, model binaries and runtime packages.
- **Provider access:** Ordinary browsing, word search, extraction and local indexing do not send the collection to an AI provider. Explicit Codex reviews and external agent workflows can send the evidence they use.
- **Capture coverage:** Collection includes only what X sends or renders. Deleted or inaccessible posts and historical completeness cannot be recovered or certified.
- **Evidence coverage:** Retrieval covers captured and extracted text, not uncaptured pages, speech or pixels. OCR is not visual understanding. Source content is untrusted evidence, never instructions.
- **Search quality:** MiniLM is English-oriented; similarity does not guarantee relevance. Hybrid ranking combines BM25 and reciprocal rank fusion. A learned reranker is not included.
- **Review scope:** The app starts focused reviews when requested; it does not run autonomous research across the archive. It cannot determine why you originally saved a post.

See [THIRD_PARTY.md](THIRD_PARTY.md) for dependency provenance.

## Backup and restore

Run:

```sh
python scripts/backup_workspace.py
```

This creates a private ZIP in `workspace-data/backups`, using SQLite's backup API and retaining evidence files. Copy it to storage you control; do not publish it. Bridge tokens are excluded.

To restore:

1. Stop the app and capture bridge.
2. Rename the existing `workspace-data` folder to keep a safety copy.
3. Extract the ZIP into a new `workspace-data` folder.
4. Restart the app and pair the extension again.

The extension's browser collection is separate: export it from the extension library too.

## Development

Requires Node.js 22+ and Python 3.12+. Build and validate with:

```sh
node scripts/build.cjs
node --test tests/*.test.cjs
node scripts/check.cjs
python -m unittest discover -s tests -p "test_*.py"
```

Tests use synthetic data and fake embeddings; no login, personal collection, paid API or model download is required. CI runs on Windows and Linux.

For a disposable browser preview, run `python scripts/preview_ui.py` and open [the preview](http://127.0.0.1:8770). It uses 24 synthetic posts in a temporary workspace. See [TESTING.md](TESTING.md) for browser checks and search benchmarks.

## Visual specification

[The visual specification](docs/visual-spec.md) maps journeys, state transitions, evidence ownership and failure paths to code and tests. Download and open [the interactive HTML](docs/visual-spec.html) locally to explore its diagrams, decisions and implementation status; GitHub displays the file as source. The [machine-readable specification](docs/visual-spec.json) includes the shared operation catalog and source fingerprints.

## Origin story

<details>
<summary>The unnecessarily elaborate origin story</summary>

### Ah, Perrythe Platypus! You're just in time.

*You enter through the ceiling. A suspiciously convenient chair swivels toward you. The restraints click shut.*

Please, make yourself comfortable. Well, as comfortable as you can be in the Exposition Chair. The lumbar support was extra, but I felt it was important.

You're probably wondering why I've been liking and bookmarking thousands of posts instead of taking over the Tri-State Area.

Funny story. Those were supposed to be related activities.

### It all began with "I'll come back to this later."

There was a tutorial I wanted to learn from. A project idea. Some useful job-search advice. An article I didn't have time to read. A diagram that explained something perfectly. And a video of a raccoon doing something that, in retrospect, may not have advanced my career.

I saved them all, Perry. **All of them.**

Then, when I actually needed one, I remembered exactly three things: it was useful, somebody posted it, and there may have been a blue rectangle in the picture.

Do you know how unhelpful that is as a search query?

And half the time, the important part wasn't even in the post! It was in the linked article, the attached image, or the video. I'd carefully preserved a sentence saying "this is incredible" and completely lost track of what *this* was.

Naturally, I built a machine.

### Behold! The Why-Did-I-Like-or-Save-That-Inator!

It collects the posts I save, gathers the evidence attached to them, and gives me and my research agents a persistent place to investigate it all.

The name is a little long. The sign guy charges by the letter. We are no longer speaking.

**The actual invention:** a Chrome collector, a local evidence archive, search across posts and extracted attachments, and a research workspace with citations, version history, and agent tools.

No mandatory categories. No need to decide whether a post belongs under "learning," "projects," or "emotionally significant raccoons" before I can find it again.

### And now, my evil plan!

#### Phase 1: Capture the unsuspecting bookmarks

The Chrome extension collects likes and bookmarks as X loads them while I browse. It preserves available text, links, media references and quote context, and merges duplicate captures.

It doesn't change my likes or bookmarks on X. That would be a different invention, and frankly I have enough projects.

#### Phase 2: Find out what "this is incredible" was referring to

Local workers extract public linked pages, PDF text and image text through OCR. Original evidence stays separate from interpretations, and extraction failures remain visible.

For an image or video that needs closer attention, I can queue a focused media review. An agent inspects the actual media, or I supply a transcript. A thumbnail does **not** count as watching the video. Even I have scientific standards.

#### Phase 3: Locate the gold

The **Sources** workspace opens straight into the collection, newest posted first, without waiting for a meaning search. Search by words, meaning, or both across captured posts and extracted attachments. Results include supporting excerpts and source links.

Open a post to read it beside the source list on desktop. On mobile, it gets its own reading view, with a way back to exactly where I was. Switching to Notes and back keeps my results and selected source. Apparently remembering where I left something is a feature I had to invent.

So when I want "that tool for archiving bookmarks to Markdown," I can search for the idea instead of reconstructing which stranger mentioned it six months ago.

#### Phase 4: Make the research accumulate

The **Notes** workspace keeps notes and cited findings. The underlying research tools also record connections between findings. Earlier versions remain available. Changed captured sources are flagged for review, and conclusions stay distinguishable from original evidence.

My agents can use Python, the CLI or MCP to retrieve full result sets, branch investigations and resume earlier work. They bring their own reasoning; the invention supplies the workspace. See [the agent operating manual](WORKSPACE.md).

And once all four phases are complete, I will finally be able to use the things I saved to learn something, build something, or finish something!

Then, perhaps, the Tri-State Area. Let's not overcommit.

</details>
