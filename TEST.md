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
- `test_main.py`
  - source resolution, output-directory helpers, PDF chunking helpers, and
    `ConversionWorker`
  - tab construction for **Settings**, **Workspace**, **Pending**, and
    **Converted**
  - workspace save/load UI plumbing
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

## Manual Smoke Checks

Run the app:

```bash
uv run python main.py
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
