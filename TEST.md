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
uv run pytest -q
```

## Automated Coverage

`test_main.py` covers unit-level behavior in `main.py`:

- `_resolve_unique_path`
  - original path when available
  - suffix incrementing (`_1`, `_2`, ...)
  - multi-dot filename handling
- `_get_source_stem`
  - local `Path` stems
  - URL stems
  - trailing slash URL behavior
- `_resolve_sources`
  - blank-line handling
  - URL acceptance
  - file-path resolution
  - directory expansion of supported file types
  - missing file and empty-supported-directory errors
- output-directory resolution helpers
  - writable local directory selection
  - URL-only fallback to Downloads
  - non-writable local directory fallback
- PDF chunking and chunk recombination helpers
- `ConversionWorker`
  - chunking flow for large PDFs
  - combined export generation
- `MainWindow._start_conversion`
  - validation error handling
  - worker creation arguments
  - UI state changes when conversion starts
  - signal connections to progress, result, and cleanup handlers
- output filename UX
  - default filename generation from the first source
  - format changes while auto mode is enabled
  - manual edits disabling auto mode
  - **Auto** button restore behavior
  - blank filename re-enabling auto mode
- `MainWindow._on_sources_changed`
  - empty output directory auto-fill behavior
  - existing manual output directory is not overwritten
- `MainWindow._on_finished`
  - done-state UI changes
  - results-table population
  - output-directory action visibility
- `MainWindow._on_worker_finished`
  - worker reference cleanup
- `MainWindow.closeEvent`
  - waits for an active worker before close

## Not Covered by Unit Tests

The following still need manual verification:

- real Docling conversion execution and first-run model downloads
- OCR/model backend behavior and hardware-specific performance
- native dialog UX (`QFileDialog.getOpenFileNames`,
  `QFileDialog.getExistingDirectory`)
- drag-and-drop interaction in `FileDropTextEdit`
- end-to-end GUI timing and race behavior under heavy conversion loads

## Manual Smoke Checks

Run the app:

```bash
uv run python main.py
```

Verify these behaviors interactively:

1. Leave output directory empty, then add a local file from a writable folder.
   Expected: the output directory auto-fills to that file's folder.
2. Leave output directory empty, then paste a URL.
   Expected: the output directory falls back to `~/Downloads` or the home
   directory fallback.
3. Leave output directory empty, then add a local file from a non-writable
   folder.
   Expected: the output directory falls back to `~/Downloads` or the home
   directory fallback.
4. Set the output directory manually, then add new sources.
   Expected: the manual output directory remains unchanged.
5. Convert a file and click **Open output directory**.
   Expected: the OS file explorer opens that directory.
6. Confirm the results table shows status, source, and target values for each
   converted item.
