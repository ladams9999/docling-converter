# Implementation for Docling Converter

## Environment Setup

All commands below assume the current working directory is the
`docling-converter` repository root.

```bash
# Install dependencies into .venv
uv sync

# Run the application
uv run docling-converter
# or
uv run python -m docling_converter
```

- Python is pinned to **3.12** in `.python-version`.
- Dependencies are managed in `pyproject.toml`.
- Use `uv` for dependency management and command execution.

## Project Structure

The application follows a standard `src` layout: importable code lives under
`src/docling_converter/`, and tests live under `tests/`.

| File | Purpose |
|------|---------|
| `src/docling_converter/main.py` | PySide6 application entry point and top-level tab orchestration |
| `src/docling_converter/conversion_logic.py` | Conversion worker, export helpers, source resolution, and PDF chunking logic |
| `src/docling_converter/workspace_model.py` | Serializable workspace state models |
| `src/docling_converter/workspace_persistence.py` | Versioned workspace save/load helpers |
| `src/docling_converter/workspace_paths.py` | Default home-based workspace path helpers |
| `src/docling_converter/workspace_ui.py` | New Workspace dialog and path resolution |
| `src/docling_converter/app_settings.py` | Application-scoped base-directory and VLM picture-description settings persistence |
| `src/docling_converter/wiki_model.py` | Serializable wiki page, import, asset, and provenance models |
| `src/docling_converter/wiki_urls.py` | URL canonicalization, scope, and flattened filename rules |
| `src/docling_converter/wiki_discovery.py` | Background wiki crawler and snapshot/asset cache |
| `src/docling_converter/wiki_conversion.py` | Cached wiki batch conversion and link rewriting |
| `src/docling_converter/wiki_ui.py` | Add Wiki dialog |
| `tests/test_main.py` | UI-level tests for tabs, queue state, conversion flow, and shared progress |
| `tests/test_workspace_model.py` | Workspace model tests |
| `tests/test_workspace_persistence.py` | Workspace persistence tests |
| `tests/test_workspace_paths.py` | Default workspace path tests |
| `tests/test_workspace_ui.py` | Workspace creation helper tests |
| `tests/test_app_settings.py` | Application settings tests |
| `tests/test_wiki_urls.py` | URL, scope, and output filename tests |
| `tests/test_wiki_discovery.py` | Crawl, redirect, cache, and asset tests |
| `tests/test_wiki_conversion.py` | Provenance, link rewrite, and batch conversion tests |
| `pyproject.toml` | Project metadata, dependencies, and hatchling build config |
| `README.md` | Human-facing documentation |
| `IMPLEMENTATION.md` | Detailed architecture and behavior notes |
| `TEST.md` | Test commands, coverage summary, and manual smoke checks |

## Working Conventions

- Keep the application simple unless complexity clearly justifies splitting it.
- Use PySide6 signals and slots for thread-safe UI updates.
- Import Docling inside the worker thread to avoid slow app startup.
- Validate user input before starting conversion.
- Keep docs aligned with the current code and test surface.

## Application Shape

`docling-converter` is still launched through `main.py`, but the app is no
longer a pure single-file implementation. Workspace state, persistence, default
paths, and conversion logic now live in focused modules that support the
workspace-oriented UI.

## Architecture Summary

The current application centers on these pieces:

- **`MainWindow`**: builds the tabbed UI and coordinates workspace state,
  queue management, save/load actions, and conversion lifecycle updates
- **`ConversionWorker`** (`conversion_logic.py`): runs Docling conversion off
  the UI thread
- **`WorkspaceData` / `WorkspaceSettings` / `ConvertedItem`**
  (`workspace_model.py`): represent persistent workspace state
- **workspace persistence/path helpers**: read/write workspace JSON and resolve
  the default home-based workspace location
- **`FileDropTextEdit`**: accepts drag-and-drop file and URL input
- **wiki import pipeline**: discovers public wiki-like HTML graphs, snapshots
  pages, and converts linked Markdown or HTML batches

## Core Components

### `MainWindow(QMainWindow)`

The main window builds the tabbed UI and coordinates workspace interaction.

Key responsibilities:

- managing tabs for **Settings**, **Workspace**, **Pending**, and **Converted**
- collecting sources from pasted text, drag-and-drop, file dialogs, and single
  URL entry
- synchronizing queue state between the Workspace and Pending surfaces
- saving and loading workspace files
- managing export format and output filename state
- starting background conversion work from the workspace-backed pending queue
- rendering shared progress state and converted-history results

### `ConversionWorker(QThread)`

The worker performs document conversion without blocking the UI thread.

Key responsibilities:

- building a `DocumentConverter` inside the worker thread via
  `_build_document_converter(vlm_settings)`, which wires in VLM picture
  description when enabled
- iterating over resolved sources
- chunking oversized PDFs before conversion when needed
- exporting each result to the requested format
- emitting progress updates and a final payload back to the main thread

### `WikiDiscoveryWorker(QThread)` and `WikiCrawler`

`WikiDiscoveryWorker` owns the GUI-facing lifecycle while `WikiCrawler` contains
the testable traversal logic. Together they:

- canonicalize and deduplicate page identities
- apply whole-wiki or sub-wiki edge rules
- validate every redirect against public-network and scope boundaries
- respect `robots.txt` unless explicitly overridden
- record outgoing page and asset URLs
- write content-addressed HTML/asset snapshots and an atomic cache manifest
- retain partial results when discovery is cancelled

### `WikiConversionWorker(QThread)`

The wiki worker reads verified snapshots rather than re-fetching pages. It plans
all output names before conversion, converts cached HTML through Docling,
rewrites links using the set of successful pages, copies verified selected
assets, adds output provenance, and emits standard result rows for Pending and
Converted integration.

### `WikiImportDialog(QDialog)`

The dialog collects the starting URL, root, whole/sub scope, `robots.txt` policy,
and asset-download choice. A root differing from the starting page requires
confirmation before discovery begins.

### `FileDropTextEdit(QPlainTextEdit)`

The custom input text area accepts dropped files and URLs and appends them to
the source list as newline-separated entries.

## Workspace Model and Persistence

### `workspace_model.py`

- `WorkspaceData`: changeable label, target directory, pending sources,
  per-source format overrides, converted items, UI settings, and wiki imports
- `WorkspaceSettings`: default export format, custom filename, and auto-name mode
- `ConvertedItem`: source/target/severity/message data for converted history

### `wiki_model.py`

- `WikiImport`: start/root URLs, scope and policy choices, pages, assets, and
  discovery timestamp
- `WikiPage`: original/canonical URLs, aliases, outgoing links, referenced
  assets, cache hash/key, inclusion state, and fetch timestamp
- `WikiAsset`: original/canonical URLs, cache hash/key, output name, and fetch
  timestamp

### `workspace_persistence.py`

- `save_workspace(...)`: writes a versioned JSON workspace file
- `load_workspace(...)`: loads and validates a versioned workspace file

### `workspace_paths.py`

- `get_app_home_directory(...)`: resolves `~/.docling-converter`
- `get_default_workspace_directory(...)`: resolves the default workspace root
- `get_default_workspace_file(...)`: resolves the default workspace JSON file
- `get_default_base_directory(...)`: resolves the default parent for new
  workspaces
- `get_default_output_directory(...)`: resolves the default output directory
- `get_wiki_cache_directory(...)`: resolves
  `~/.docling-converter/cache/wiki/<import-id>`

## Conversion and Helper Functions

Ordinary document conversion logic lives in `conversion_logic.py`, including:

- `ConversionWorker`
- `_resolve_unique_path(directory, filename)`
- `_get_source_stem(source)`
- `_resolve_sources(raw_text)`
- `_is_writable_directory(directory)`
- `_get_downloads_directory()`
- `_resolve_auto_output_directory(sources)`
- `_is_pdf_source(source)`
- `_download_pdf_url(url)`
- `_get_pdf_page_count(pdf_path)`
- `_get_file_size_mb(file_path)`
- `_should_chunk_pdf(page_count, size_mb)`
- `_split_pdf_into_chunks(pdf_path, chunk_size)`
- `_export_document(doc, key)`
- `_extract_html_body(html)`, `_merge_json_values(...)`,
  `_combine_chunk_contents(...)`
- `_build_document_converter(vlm_settings)`

## Supported Formats

### Input

- PDF
- Microsoft Word (`.docx`)
- Microsoft PowerPoint (`.pptx`)
- Microsoft Excel (`.xlsx`)
- HTML
- Images (`.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`)
- LaTeX
- Markdown
- EPUB (`.epub`)
- Plain text (`.txt`)

### Output

- Markdown
- HTML
- JSON
- DocTags

Wiki batches currently allow only Markdown and HTML. JSON and DocTags remain
available for ordinary files and single URLs.

## Picture Description (VLM)

`_build_document_converter(vlm_settings)` in `conversion_logic.py` wires
docling's `PictureDescriptionApiOptions` into the PDF/image pipelines when
enabled in Settings (`app_settings.VlmSettings`). It targets any
OpenAI-compatible chat-completions endpoint (`api_url`/`model`/`api_key`),
defaulting to a local Ollama server running `granite3.2-vision:2b` — no
docling-side code changes are needed to switch models or providers, only the
Settings fields. Disabled by default; other formats (DOCX, HTML, etc.) are
unaffected regardless of this setting since they don't go through the
picture-detecting PDF/image pipelines.

## UI Layout

The main window now uses top-level tabs:

1. **Settings**
   - persistent workspace base directory
   - default export format selector
   - picture description (VLM) toggle, API URL, model, and API key fields
2. **Workspace**
   - changeable label and workspace file display
   - **New workspace...**, **Load workspace...**, and **Save workspace...**
   - source input area plus an Input files table with per-file formats
   - derived Output files list and output filename field with **Auto**
   - output directory field and picker
   - **Convert** action, shared status, output-directory display, and results table
3. **Pending**
   - shared processing state
   - queue controls for files, directories, single URLs, and wiki discovery
   - queue list
   - **Convert pending**, remove, and clear actions
4. **Converted**
   - shared processing state
   - converted-history table

## Queue and Workspace Behavior

- The pending queue is stored in `WorkspaceData.pending_sources`.
- The Workspace tab input and Pending tab list stay synchronized.
- Saving a workspace persists its label, pending sources, per-source formats,
  converted history, target directory, and selected UI settings.
- Loading a workspace restores those values into the UI.
- Successful conversions are appended to converted history and removed from the
  pending queue.
- Removing a wiki page excludes it while preserving its graph metadata and
  snapshot reference in the workspace.

## Wiki Import

- **Whole wiki** recursively follows eligible same-origin links under a confirmed
  root.
- **Sub-wiki** includes the starting page, recursively follows child-directory
  links, and follows same-directory links one level from the starting page.
- Canonical URL tracking prevents loops; discovery has no page-count cap and can
  be cancelled.
- `robots.txt` is respected by default with an explicit override.
- Only public, authentication-free HTTP/HTTPS sites are supported. Private,
  loopback, link-local, and credential-bearing destinations are rejected.
- Discovery snapshots normalized HTML, outgoing links, original URL, UTC fetch
  timestamp, and optional assets in the application cache.
- Workspace version `3` persists labels and per-source formats while loading
  version `1` and `2` workspaces.
- Wiki conversion supports Markdown and HTML, uses deterministic flattened
  filenames, and rewrites links only for successfully converted pages.
- Markdown receives YAML `original_url`/`fetched_at` frontmatter. HTML receives a
  leading comment with the same provenance.
- Optional assets are copied to `<output>/assets`; otherwise their web URLs
  remain absolute.
- All wiki page and selected-asset conflicts are displayed before overwrite.
- Wiki pages and ordinary sources must be converted in separate batches.

### URL Identity and Scope

- Scheme and hostname are normalized; default ports, fragments, and known
  tracking parameters do not create duplicate page identities.
- Other sorted query parameters remain part of identity.
- Redirect aliases map to one canonical page.
- Whole-wiki traversal requires the same origin and root path boundary.
- Sub-wiki traversal recursively accepts child-directory pages and accepts
  same-directory pages only when linked directly from the starting page.

### Cache Layout

Each import uses:

```text
~/.docling-converter/cache/wiki/<import-id>/
  manifest.json
  pages/<sha256>.html
  assets/<sha256>.<extension>
```

Workspace JSON stores cache keys and SHA-256 hashes, not HTML bodies. Conversion
rejects missing, path-traversing, or hash-mismatched cache entries instead of
silently fetching changed content.

### Wiki Output Planning

The path relative to the confirmed root is flattened with `-`, terminal
`.html`/`.htm` is removed, directory pages receive `index`, and Windows-invalid
or reserved names are sanitized. Case-insensitive collisions and query-distinct
pages receive stable URL-hash suffixes.

Only successfully converted pages are included in the final local-link map.
Excluded or failed destinations remain absolute. Selected assets are globally
deduplicated and copied beneath `assets/`; failed asset copies remain remote and
produce warnings.

Markdown starts with:

```yaml
---
original_url: "https://example.com/wiki/page"
fetched_at: "2026-07-12T18:00:00Z"
---
```

HTML starts with the same fields in a comment before the doctype or content.

## Output Directory Behavior

- If the output directory is already set, source edits do not overwrite it.
- If the output directory is empty and valid sources are added:
  - the first writable local source directory is preferred
  - URL-only input falls back to the user's Downloads directory
  - non-writable local directories also fall back to Downloads
- The completed output directory is stored so the open-folder action can launch
  the native file explorer.

## Output Filename Behavior

- The default output filename is derived from the first resolved source and the
  selected export extension.
- Changing the export format updates the default filename while auto mode is
  enabled.
- Manual edits disable automatic filename updates.
- Clearing the filename or pressing **Auto** restores auto-generated naming.

## Conversion Flow

1. The main window validates the workspace-backed pending queue and output
   directory.
2. It creates `ConversionWorker` with the resolved queued sources, output
   directory, selected format, and optional custom filename.
3. The worker converts each source and writes the output file.
4. The main thread updates shared progress state, the workspace results table,
   and the converted-history table from worker signals.
5. Successfully converted items are removed from the pending queue and stored in
   workspace history.
6. Temporary files and PDF chunk directories are cleaned up after each source.

### Wiki Conversion Flow

1. Validate that the queue contains only wiki pages and the selected format is
   Markdown or HTML.
2. Plan deterministic page and selected-asset names.
3. Display every existing target conflict and continue only after confirmation.
4. Verify cached hashes and convert snapshots into temporary outputs.
5. Build the final target map from successful conversions.
6. Rewrite local page/asset links, add provenance, and finalize outputs.
7. Move successes to Converted while failed pages remain Pending.

## PDF Chunking

Large PDFs are chunked before conversion when either threshold is exceeded:

- page count greater than `30`
- file size greater than `5 MB`

Chunks are converted individually and then recombined into a single exported
result. This keeps large conversions more manageable while preserving a single
output artifact per source.

## Testing Surface

Automated tests live across the workspace tests, `test_main.py`, and focused
`test_wiki_*.py` modules. They cover
workspace state, persistence, path helpers, queue management, tab
construction, shared progress, converted history, helper behavior, worker
logic, UI validation, auto filename state, output-directory selection,
results-table population, and worker cleanup behavior.

See `TEST.md` for exact test commands, automated coverage details, and manual
smoke coverage.
