# Testing for Docling Converter

## Prerequisites

Run these commands from the `docling-converter` repository root.

- Python 3.12+
- `uv`
- Dependencies installed:

```bash
uv sync
```

## Run All Tests

```bash
uv run python -m pytest -q
```

## Automated Coverage

Automated coverage currently includes:

- `test_workspace_model.py`
  - default workspace model values
  - nested workspace/settings/converted-item round-tripping
  - converted-item normalization behavior
- `test_workspace_persistence.py`
  - versioned JSON save/load round-tripping
  - version stamping
  - unsupported-version rejection
- `test_workspace_paths.py`
  - app-home path resolution
  - default workspace/output/file path conventions
- `test_workspace_ui.py`
  - workspace label slugging and workspace filename resolution
- `test_app_settings.py`
  - application base-directory persistence
- `test_wiki_urls.py`
  - URL canonicalization, root/scope rules, sub-wiki traversal, safe flattened
    filenames, and deterministic collisions
- `test_wiki_discovery.py`
  - cyclic graph discovery, snapshots, provenance, sub-wiki depth, redirect
    aliases/boundaries, and optional assets
- `test_wiki_conversion.py`
  - Markdown/HTML provenance helpers, safe link rewriting, cached conversion,
    balanced-parenthesis URLs, and overwrite conflict planning
- `test_main.py`
  - source resolution, output-directory helpers, PDF chunking helpers, and
    `ConversionWorker`
  - tab construction for **Settings**, **Workspace**, **Pending**, and
    **Converted**
  - workspace save/load UI plumbing
  - new workspace creation and per-input output format planning
  - pending-queue expansion, add/remove behavior, and queue-backed conversion
    startup
  - shared progress/status propagation across tabs
  - converted-history updates and queue draining on completion
  - output filename UX
  - validation error handling
  - worker cleanup behavior on close

## Not Covered by Unit Tests

The following still need manual verification:

- real Docling conversion execution and first-run model downloads
- OCR/model backend behavior and hardware-specific performance
- native dialog UX (`QFileDialog.getOpenFileNames`,
  `QFileDialog.getExistingDirectory`, workspace open/save dialogs)
- drag-and-drop interaction in `FileDropTextEdit`
- end-to-end GUI timing and race behavior under heavy conversion loads
- real public-site discovery behavior, `robots.txt`, and network failure timing

## Manual Smoke Checks

Run the app:

```bash
uv run docling-converter
```

Verify these behaviors interactively:

1. Add a local file on the **Workspace** tab with an empty output directory.
   Expected: the output directory auto-fills to that file's folder.
2. Add a URL on the **Workspace** or **Pending** surface with an empty output
   directory.
   Expected: the output directory falls back to `~/Downloads` or the home
   directory fallback.
3. Save a workspace, close the app, relaunch it, and load that workspace.
   Expected: pending sources, output directory, selected format, filename mode,
   and converted history restore correctly.
4. Add files, a directory, and a single URL on the **Pending** tab.
   Expected: the queue expands supported directory contents and displays all
   pending sources.
5. Convert a queued file and click **Open output directory**.
   Expected: the OS file explorer opens that directory, the item disappears
   from **Pending**, and it appears in **Converted**.
6. Confirm the shared processing state updates on the **Workspace**,
   **Pending**, and **Converted** tabs during an active conversion.
7. Import `https://foundryvtt.com/api/v13/` as a whole wiki, confirm the inferred
   root, cancel once, then rediscover and review Pending pages.
8. Import
   `https://www.dandwiki.com/wiki/Hyrule_(5e_Campaign_Setting)` as a sub-wiki.
   Expected: the starting page, child-directory pages, and one level of
   same-directory links are queued without loops.
9. Convert a small wiki selection to Markdown and HTML. Expected: flattened
   filenames, local links, and `original_url`/`fetched_at` provenance are present.
10. Repeat with assets enabled and an existing target file. Expected: assets are
    written below `assets/`, and the full conflict list requires confirmation.
11. Enable "Describe pictures during conversion" on **Settings** (defaults
    target a local Ollama server) and convert a PDF or image containing a
    picture. Expected: the output includes a generated caption beneath the
    `<!-- image -->` placeholder, and the row shows **success**, not
    **warning** (docling's internal deprecation notices from the
    picture-description path are filtered, not surfaced).
