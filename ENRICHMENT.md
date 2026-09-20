# Attachment enrichment

Install requirements-enrichment.txt into .runtime, then run `python scripts/enrich_library.py --run`. This creates/resumes deduplicated public-link and image jobs with checkpointed failures. Inspect `enrichment_status`, `job`, and `retry_job` through the CLI for details. Plan again after new captures with `plan_enrichment`; existing cached URLs do not automatically refetch.

HTML uses article extraction with a fallback parser. PDF extraction covers the first 300 text-layer pages, not scanned-page OCR. Images use local RapidOCR, resized to at most 1800 pixels per side, retaining recognized lines, coordinates and scores. Non-English, stylized and small text may be missed. Raw downloads are retained by content hash.

Downloads validate public addresses and pin DNS on redirects. They use no browser cookies or account credentials. The per-response limit is 12 MB. Unsupported formats, access failures and parse failures remain explicit errors. X and YouTube HTML is excluded from attachment body search because login/navigation pages are not post context or video transcripts.

Visual interpretations and imported transcripts remain distinct derived observations attached to their source. Use request_media and complete_media for focused tasks. Video/audio acquisition, automatic transcription, authenticated thread expansion and remote cache refresh require additional adapters; they are not silently performed. Existing video thumbnails do not become playable videos. The extension preserves playable variants when supplied in newly observed responses.

Run `index_attachments` after enrichment to update meaning search. Keyword search sees new evidence immediately. Full passage coverage means all cleaned extracted text, not all content that ever existed at a link.
