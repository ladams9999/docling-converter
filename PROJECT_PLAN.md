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
  current unit-test surface.
- Validate generic discovery against representative real-world wiki-like sites.
- Evaluate authenticated/private wiki support and additional wiki export formats
  only after their security and output semantics are designed.
- Improve contributor guidance so future work can be picked up quickly.

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
