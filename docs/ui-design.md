# Workspace UI

The interface is a local source-and-notes workspace. Chalk-white reading surfaces sit within a fine instrument-like frame. Aubergine details, yellow-green selections, and amber keeping actions give it a consistent identity. The compact inator signature retains the full product name in its accessible label and tooltip. The invention joke stays in the identity and help copy; functional labels stay plain. No external fonts, UI frameworks, or new runtime dependencies are required.

## Organization

- **Sources** and **Notes** are the two primary navigation links in a shallow header. **Review queue** is a secondary destination for unfinished media work. There is no permanent sidebar.
- Sources opens with current posts ordered by posted date, newest first, with undated posts last. Browsing does not run the semantic model. Search supports words, meaning, or both; Browse all returns to the collection.
- Scan presents compact source excerpts in aligned rows. Read presents fuller cards. Read post selects a source in a separate desktop reading pane. On mobile, the reader occupies the working surface; Back to list restores the previous list position and focus.
- Notes holds saved notes and cited findings. Source-specific note and review actions stay with the source. New note is available in the application header.
- The mobile header uses two short rows: identity and review access, then primary navigation and New note. Collection status and help live in the footer. An accessible page heading remains without repeating the selected destination visually.

## Interaction rules

- Each destination retains query drafts, rendered results, loaded pages, expanded evidence, and scroll position while the page stays open. Sources also retains the selected reader. Switching destinations does not repeat a source search. Requests finish into their own destination; stale responses cannot overwrite newer searches.
- Refresh results explicitly fetches fresh data. Saving a note or requesting a review invalidates the relevant destination. A new source search clears the previous selection. Native links support direct destination URLs and browser Back.
- Source content is rendered as text, never trusted markup. Evidence labels distinguish post text, linked pages, OCR, thumbnail text, transcripts, and interpretations. Missing dates are explicit. Retrieval details report actual counts, search method, completion time, and elapsed time.
- Add to note accumulates exact source spans without duplicating the same span. Individual citations can be removed. Browse excerpts are bounded; the reader preserves full captured post text.
- The note dialog retains its draft and sources in the tab's session storage across reloads. This is temporary draft storage, not a cross-device backup. Save note writes to the workspace; closing the editor does not discard the draft. Editing is locked during a save.
- Native dialogs provide focus containment and Escape behavior. Keyboard users can skip navigation or press `/` to focus search. Visible focus indicators and reduced-motion preferences remain available.
- Review requests explain that an agent or person must inspect the media. Completed reviews remain readable. A thumbnail is never presented as understanding the whole video.
- Empty results suggest a next step. Requests show progress, prevent duplicate submissions, and offer recovery on failure.

## Visual principles

Proportional sans-serif typography carries headings and source prose; monospace is reserved for ordinals, counts, and retrieval details. Rules and alignment distinguish regions without turning every record into an isolated decorative card. Aubergine anchors primary actions and structural details; yellow-green identifies selection; amber marks keeping evidence. The header uses neutral surfaces with small active-destination indicators. An original fragments/stack/find motif repeats the colors of the Sources → Evidence → Notes guide. A stippled divider adds texture without covering reading surfaces. Controls share modest corner radii. Reading takes priority over introductory artwork and repeated headings.

References that informed the design:

- [U.S. Graphics](https://usgraphics.com/): information density, explicit controls, and visible system state.
- [General Catalog](https://usgraphics.com/catalog): consistent alignment and comparable fields.
- [Berkeley Mono](https://usgraphics.com/products/berkeley-mono): typography as a reading instrument. No U.S. Graphics font or artwork is bundled.
- [Neil Panchal on Spotify](https://neil.computer/notes/dear-spotify-can-we-just-get-table-of-songs/): identifying information should take precedence over decorative cover art.
- [Neil Panchal on JetBrains](https://neil.computer/notes/dear-jetbrains-dont-mess-with-your-ui/): stable interaction patterns and learned positions matter.
- [The Design of Diskprices.com](https://neil.computer/notes/the-design-of-diskprices-com/): devote screen space to the user's task.

These are sources of inspiration, not an endorsement or a claim that their authors designed this application.

## Verification

See [TESTING.md](../TESTING.md) for commands and the browser acceptance checklist. `python scripts/preview_ui.py` serves the real UI at `http://127.0.0.1:8770` against a disposable 24-post synthetic collection. Stop with Ctrl+C.

Controller tests exercise navigation and request lifecycles with a small DOM adapter. Browser checks cover desktop list/reader layouts, narrow mobile navigation, note dialogs, review workflows, and overflow at 320px. Visual checks complement the tests; they are not automated browser coverage. Personal collection measurements and captured content do not belong in this document.

The footer contains an expandable “Inside the invention” guide and a LOCAL version plate. The plate reflects package.json; scripts/check.cjs rejects a mismatched version. The outer margin and frame collapse on mobile to preserve space.
