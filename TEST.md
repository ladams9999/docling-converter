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
- `MainWindow._on_finished`
  - done-state UI changes
  - preview behavior for HTML/Markdown/plain-text paths
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
- Visual rendering fidelity details of rich preview content across formats
- Full interactive GUI click-flow verification of filename auto/manual mode transitions
