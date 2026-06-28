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
| `main.py` | Single-file PySide6 application entry point |
| `test_main.py` | Unit tests for helpers, worker logic, and UI state handling |
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

`docling-converter` is currently a single-file PySide6 desktop application in
`main.py`. The project favors a simple structure, with a split into multiple
modules deferred until complexity clearly warrants it.

## Architecture Summary

The application currently lives in `main.py` and centers on three pieces:

- **`MainWindow`**: builds the UI and manages user interactions
- **`ConversionWorker`**: runs Docling conversion off the UI thread
- **`FileDropTextEdit`**: accepts drag-and-drop file and URL input

## Core Components

### `MainWindow(QMainWindow)`

The main window builds the UI and coordinates user interaction.

Key responsibilities:

- collecting sources from pasted text, drag-and-drop, and file dialogs
- selecting and displaying the output directory
- managing export format and output filename state
- starting background conversion work
- rendering completion state and per-file results

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

## Helper Functions

- `_resolve_unique_path(directory, filename)`: adds `_1`, `_2`, and so on when a
  target file already exists
- `_get_source_stem(source)`: derives a default output stem from a local path or
  URL
- `_resolve_sources(raw_text)`: parses input lines into local `Path` values or
  URLs and collects validation errors
- `_is_writable_directory(directory)`: checks whether an output directory is
  writable
- `_get_downloads_directory()`: resolves the user's Downloads directory with a
  home-directory fallback
- `_resolve_auto_output_directory(sources)`: chooses an output directory from
  the first writable local source or falls back to Downloads
- `_is_pdf_source(source)`: identifies PDF paths and PDF URLs
- `_download_pdf_url(url)`: downloads a remote PDF to a temporary local file
- `_get_pdf_page_count(pdf_path)`: reads PDF page count with `pypdf`
- `_get_file_size_mb(file_path)`: measures PDF size
- `_should_chunk_pdf(page_count, size_mb)`: decides whether a PDF should be
  chunked before conversion
- `_split_pdf_into_chunks(pdf_path, chunk_size)`: creates temporary PDF chunks
- `_export_document(doc, key)`: exports a Docling document in the selected
  format
- `_extract_html_body(html)`, `_merge_json_values(...)`,
  `_combine_chunk_contents(...)`: recombine chunk output into a final artifact

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

Top to bottom, the window contains:

1. Input group with a multi-line source field plus **Browse files...** and
   **Clear** actions
2. Output directory field with a native directory picker
3. Export format selector and output filename row
4. **Convert** action and indeterminate progress bar
5. Status label
6. Output-directory display row with **Open output directory**
7. Results table with `Status`, `Source`, and `Target` columns

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

1. The main window validates sources and output directory.
2. It creates `ConversionWorker` with the resolved sources, output directory,
   selected format, and optional custom filename.
3. The worker converts each source and writes the output file.
4. The main thread updates the status label and results table from worker
   signals.
5. Temporary files and PDF chunk directories are cleaned up after each source.

## PDF Chunking

Large PDFs are chunked before conversion when either threshold is exceeded:

- page count greater than `30`
- file size greater than `5 MB`

Chunks are converted individually and then recombined into a single exported
result. This keeps large conversions more manageable while preserving a single
output artifact per source.

## Testing Surface

Automated tests live in `test_main.py` and cover helper behavior, worker logic,
UI validation, auto filename state, output-directory selection, results-table
population, and worker cleanup behavior.

See `TEST.md` for exact test commands, automated coverage details, and manual
smoke coverage.
