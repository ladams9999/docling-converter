# Pending Tasks for Docling Converter

Tasks below are intentionally small and individually pickable.

---

## In progress: EPUB + plain-text input support

Working on branch `docling-converter-work-plan`
(worktree: `../docling-wt-work-plan`), per
`../docling-converter-work-plan.md` priority tasks 1–2. **Status: blocked on
user design decisions below** — no code written yet.

**Findings** (installed `docling` 2.75, checked via
`docling-converter/.venv`):

- `docling`'s `DocumentConverter` has **no native EPUB backend at all**
  (`InputFormat` has no epub member; `docling/backend/` has no epub module).
  The work plan's phrasing ("wire a conversion path through Docling")
  undersold this — it's new adapter code, not just registering an extension.
- `docling` also has **no plain-text `InputFormat`**. Worse, its own
  `FormatToExtensions` table already maps `.txt` to `InputFormat.XML_USPTO`
  (the patent-XML backend) as a side effect of that format's extension list —
  passing a plain `.txt` file to `converter.convert()` today would silently
  route it to the wrong backend and likely fail or produce garbage, not just
  "unsupported extension."

**Candidate approach** (not yet built, needs sign-off):

- **Plain text**: write the source to a temp file with a `.md` extension
  before calling `converter.convert()`, forcing docling's Markdown backend
  (`InputFormat.MD`) to handle it — plain prose is valid structureless
  CommonMark, so this should round-trip cleanly. Mirrors the existing
  temp-file pattern already used for downloaded PDF URLs in
  `conversion_logic.py` (`temp_files` cleanup list).
- **EPUB**: no backend to force it into directly. Best option found: add
  `ebooklib` as a new dependency, use it to pull each spine item's XHTML out
  of the `.epub` container, run each chapter through docling's existing HTML
  backend, and stitch the results together with `_combine_chunk_contents()`
  — the function already in `conversion_logic.py` that merges multi-chunk
  PDF output. Structurally this is the same shape as the existing
  PDF-chunking flow (`conversion_targets = [...]`, `chunked = True`), just
  chunked by chapter instead of by page range.

**Open questions for the user** (asked live in the session that wrote this
note — check chat history/PR discussion before re-asking):

1. Does the temp-`.md`-rename approach for plain text seem right, or is
   there a preferred alternative?
2. Does the `ebooklib` + per-chapter-HTML + `_combine_chunk_contents()`
   approach for EPUB seem right, given no native docling backend exists?
3. How should EPUB-sourced content be labeled/handled in the Workspace UI
   (per the work plan — no existing convention to match since EPUB wasn't
   supported before)?

- See `PROJECT_PLAN.md`'s **Upcoming Goals** for larger, gated, or
  not-yet-scheduled directions (packaging/distribution, authenticated/private
  wiki support, wiki JSON/DocTags export, site-specific wiki adapters,
  extracting `main.py`) — promote an item here once it's unblocked and small
  enough to pick up directly.
- See `test-coverage-plan.md` for the ongoing expansion of GUI/interactive
  test coverage (drag-and-drop, native dialogs, multi-step flows) — tracked
  there as a living checklist rather than here, since it's continuous rather
  than a single pickable item.
