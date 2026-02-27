# Testing Guide

## Prerequisites

- Python 3.12+
- `uv`
- Dependencies installed:

```bash
uv sync
```

## Run all tests

Use this command to run the full test suite:

```bash
uv run pytest -q
```

## What is under test

`test_main.py` covers unit-level behavior in `main.py`:

- `_resolve_unique_path`
  - original path when available
  - suffix incrementing (`_1`, `_2`, ...)
  - multi-dot filename handling
- `_get_source_stem`
  - local `Path` stems
  - URL stems
  - trailing slash URL returns the last path segment stem
- `_resolve_sources`
  - blank-line handling
  - URL acceptance
  - file-path resolution
  - directory expansion of supported file types
  - missing file and empty-supported-directory errors
- `MainWindow._start_conversion`
  - validation error handling
  - worker creation args
  - UI state changes when conversion starts
  - signal connections to progress/result/cleanup handlers
- Output directory auto-selection behavior
  - empty output directory auto-fills when sources are added
  - first local source directory is used when writable
  - URL-only input falls back to user's Downloads directory
  - non-writable local source directory falls back to Downloads
  - existing non-empty output directory is never auto-overwritten
- `MainWindow._on_finished`
  - done-state UI changes
  - results table population (`Status`, `Source`, `Target`)
  - `Open output directory` button visibility when output directory exists
- `MainWindow._on_worker_finished`
  - worker reference cleanup
- `MainWindow.closeEvent`
  - waits on active worker thread before close
- Output filename auto-mode UX
  - default filename generation from first input source + selected export format
  - format changes update filename while auto mode is enabled
  - manual filename edits disable auto updates
  - `Auto` button restores generated default and re-enables auto mode
  - clearing the filename re-enables auto mode

## User flows not under test

The following are intentionally outside this unit test scope and should be verified manually:

- Real `docling` conversion execution and model downloads from Hugging Face
- OCR/model backend behavior and hardware-specific performance
- Native dialog UX (`QFileDialog.getOpenFileNames`, `getExistingDirectory`)
- Drag-and-drop event behavior in `FileDropTextEdit`
- Full end-to-end threading timing/race behavior under heavy conversion loads
- Full interactive GUI click-flow verification of filename auto/manual mode transitions

## Manual smoke checks for latest output-directory UX

Run the app:

```bash
uv run python main.py
```

Verify these behaviors interactively:

1. Leave output directory empty, add a local file from a writable folder.
  - Expected: output directory auto-fills to that file's folder.
2. Leave output directory empty, paste a URL.
  - Expected: output directory auto-fills to `~/Downloads` (or home fallback).
3. Leave output directory empty, add a local file from a non-writable folder.
  - Expected: output directory falls back to `~/Downloads` (or home fallback).
4. Set output directory manually, then add new sources.
  - Expected: manual output directory remains unchanged.
5. Convert a file and click **Open output directory** beside the output directory display row.
  - Expected: OS file explorer opens that directory.
6. Confirm results table rows show status icon, full source path/URL, and target filename.
