# Implementation for Docling Converter

## Environment Setup

All commands below assume the current working directory is the
`docling-converter` repository root.

```bash
# Install dependencies into .venv
uv sync

# Run the application
uv run python main.py
```

- Python is pinned to **3.12** in `.python-version`.
- Dependencies are managed in `pyproject.toml`.
- Use `uv` for dependency management and command execution.

## Project Structure

| File | Purpose |
|------|---------|
| `main.py` | PySide6 application entry point and top-level tab orchestration |
| `conversion_logic.py` | Conversion worker, export helpers, source resolution, and PDF chunking logic |
| `workspace_model.py` | Serializable workspace state models |
| `workspace_persistence.py` | Versioned workspace save/load helpers |
| `workspace_paths.py` | Default home-based workspace path helpers |
| `test_main.py` | UI-level tests for tabs, queue state, conversion flow, and shared progress |
| `test_workspace_model.py` | Workspace model tests |
| `test_workspace_persistence.py` | Workspace persistence tests |
| `test_workspace_paths.py` | Default workspace path tests |
| `pyproject.toml` | Project metadata and dependencies |
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

The current application centers on five pieces:

- **`MainWindow`**: builds the tabbed UI and coordinates workspace state,
  queue management, save/load actions, and conversion lifecycle updates
- **`ConversionWorker`** (`conversion_logic.py`): runs Docling conversion off
  the UI thread
- **`WorkspaceData` / `WorkspaceSettings` / `ConvertedItem`**
  (`workspace_model.py`): represent persistent workspace state
- **workspace persistence/path helpers**: read/write workspace JSON and resolve
  the default home-based workspace location
- **`FileDropTextEdit`**: accepts drag-and-drop file and URL input

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

- importing `DocumentConverter` inside the worker thread
- iterating over resolved sources
- chunking oversized PDFs before conversion when needed
- exporting each result to the requested format
- emitting progress updates and a final payload back to the main thread

### `FileDropTextEdit(QPlainTextEdit)`

The custom input text area accepts dropped files and URLs and appends them to
the source list as newline-separated entries.

## Workspace Model and Persistence

### `workspace_model.py`

- `WorkspaceData`: target directory, pending sources, converted items, and UI
  settings
- `WorkspaceSettings`: selected export format, custom filename, and auto-name
  mode
- `ConvertedItem`: source/target/severity/message data for converted history

### `workspace_persistence.py`

- `save_workspace(...)`: writes a versioned JSON workspace file
- `load_workspace(...)`: loads and validates a versioned workspace file

### `workspace_paths.py`

- `get_app_home_directory(...)`: resolves `~/.docling-converter`
- `get_default_workspace_directory(...)`: resolves the default workspace root
- `get_default_workspace_file(...)`: resolves the default workspace JSON file
- `get_default_output_directory(...)`: resolves the default output directory

## Conversion and Helper Functions

Most conversion logic now lives in `conversion_logic.py`, including:

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

### Output

- Markdown
- HTML
- JSON
- DocTags

## UI Layout

The main window now uses top-level tabs:

1. **Settings**
   - export format selector
   - output filename field with **Auto**
2. **Workspace**
   - workspace file display
   - **Load workspace...** / **Save workspace...**
   - source input area with drag/drop plus **Browse files...** and **Clear**
   - output directory field and picker
   - **Convert** action, shared status, output-directory display, and results table
3. **Pending**
   - shared processing state
   - queue controls for files, directories, and single URLs
   - queue list
   - **Convert pending**, remove, and clear actions
4. **Converted**
   - shared processing state
   - converted-history table

## Queue and Workspace Behavior

- The pending queue is stored in `WorkspaceData.pending_sources`.
- The Workspace tab input and Pending tab list stay synchronized.
- Saving a workspace persists pending sources, converted history, target
  directory, and selected UI settings.
- Loading a workspace restores those values into the UI.
- Successful conversions are appended to converted history and removed from the
  pending queue.

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

## PDF Chunking

Large PDFs are chunked before conversion when either threshold is exceeded:

- page count greater than `30`
- file size greater than `5 MB`

Chunks are converted individually and then recombined into a single exported
result. This keeps large conversions more manageable while preserving a single
output artifact per source.

## Testing Surface

Automated tests live across `test_main.py`, `test_workspace_model.py`,
`test_workspace_persistence.py`, and `test_workspace_paths.py`. They cover
workspace state, persistence, path helpers, queue management, tab
construction, shared progress, converted history, helper behavior, worker
logic, UI validation, auto filename state, output-directory selection,
results-table population, and worker cleanup behavior.

See `TEST.md` for exact test commands, automated coverage details, and manual
smoke coverage.
