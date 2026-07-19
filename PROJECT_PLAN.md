# Project plan for Docling Converter

## Project Overview

Docling Converter is a PySide6 desktop application that wraps
[Docling](https://github.com/docling-project/docling) in a native GUI. Users can
convert individual files and URLs or discover public wiki-like sites for linked
Markdown and HTML export.

## Primary Goals

- Keep Docling Converter easy to run locally as a lightweight desktop utility.
- Preserve a responsive GUI while running potentially heavy document conversion
  work in the background.
- Support common document and image inputs with consistent export behavior
  across Markdown, HTML, JSON, and DocTags output.
- Preserve link structure and source provenance when exporting wiki collections.
- Keep the project approachable for contributors by documenting architecture,
  testing, and follow-up work clearly.

## Current Product Direction

- Maintain the PySide6 desktop workflow as the primary interface.
- Continue favoring a simple repository layout while documenting where the
  boundaries are if the app needs to be split into multiple modules.
- Preserve quality-of-life features already present in the app, including:
  - automatic output-directory selection
  - automatic output filename generation with manual override
  - conversion status reporting and results-table summaries
  - PDF chunking for large inputs
  - cached whole-wiki and sub-wiki discovery
  - deterministic flattened wiki filenames and local link rewriting

## Near-Term Priorities

- Keep the documentation set aligned with the actual code and tests.
- Strengthen confidence around desktop-specific flows that remain outside the
  current unit-test surface — ongoing, tracked as a living checklist in
  `test-coverage-plan.md`.
- Validate generic discovery against representative real-world wiki-like sites.
- Improve contributor guidance so future work can be picked up quickly.

## Upcoming Goals

Larger or gated directions that are valid but not yet small/pickable work.
Promote an item to `PENDING_TASKS.md` once its prerequisites are resolved and
it can be broken into a concrete, individually pickable task.

- **Packaging and distribution.** Document, and eventually automate, building
  and releasing Docling Converter for non-developer desktop users. No
  distribution mechanism (installer, code signing, PyInstaller/equivalent)
  exists yet — revisit once there's an actual need to hand this app to someone
  outside a dev environment.
- **Authenticated/private wiki support** (`wiki-plan.md` Q6). Gated on
  designing credential storage and private-network access policy first; the
  crawler currently blocks localhost/private-network targets by default and
  only supports unauthenticated public sites.
- **JSON and DocTags wiki export** (`wiki-plan.md` Q9). Wiki batches currently
  support Markdown and HTML only; JSON/DocTags need their own link/output
  rewriting semantics defined before they're added.
- **Site-specific wiki adapters** (`wiki-plan.md` Q3). Only worth building if
  generic path/link-based traversal proves insufficient against a real site —
  no evidence of that yet.
- **Extract `main.py` into focused modules.** Currently a single ~1,260-line
  file; wiki-specific logic has already been split out into `wiki_ui.py`,
  `wiki_conversion.py`, `wiki_discovery.py`, etc. Revisit once further growth
  (or a specific maintenance pain point) makes the remaining single-file
  structure genuinely costly to work in — not a fixed line-count trigger.

## Current Application State

### Workspace

- Workspace context includes a changeable label, target directory, pending
  sources, per-source export formats, converted history, settings, and wiki
  graphs.
- New workspaces are seeded from a label and application base directory.
  Workspace version `3` loads existing version `1` and `2` files.
- The default workspace and wiki cache use directories under
  `~/.docling-converter`.

### User Interface

- **Settings** controls the workspace base directory and default export format.
- **Workspace** controls workspace creation, labels, files, sources, per-file
  formats, planned outputs, and target directory.
- **Pending** supports files, directories, single URLs, wiki discovery, queue
  removal, progress, and cancellation.
- **Converted** records successful output history and shared processing state.

### Standard Conversion

- Local files, supported directory contents, and individual HTTP/HTTPS URLs can
  be queued.
- Markdown, HTML, JSON, and DocTags are supported for ordinary sources.
- Large PDFs are split for conversion and recombined into one output.

### Wiki Import

- Whole-wiki discovery follows eligible links recursively beneath a confirmed
  root.
- Sub-wiki discovery includes the starting page, recursively follows linked
  child directories, and includes one level of same-directory links.
- Discovery targets public, authentication-free HTTP/HTTPS sites, tracks
  canonical URLs to stop loops, respects `robots.txt` by default, and can be
  cancelled.
- Fetched pages and optional assets are snapshot-cached for reproducible offline
  conversion.
- Users review and remove discovered pages in Pending before conversion.
- Wiki batches export Markdown or HTML with deterministic flattened path-based
  names and links rewritten between successful local outputs.
- Markdown uses YAML provenance; HTML uses a leading provenance comment. Both
  record `original_url` and the UTC `fetched_at` timestamp.
- Existing page and selected-asset conflicts require explicit overwrite
  confirmation.
- See `wiki-plan.md` for scope rules, decisions, implications, and acceptance
  criteria.
