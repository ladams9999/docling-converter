# AGENTS.md - docling-converter

Instructions for AI agents (or humans) working on this project.

## Project Overview

This is a **PySide6 desktop application** (`main.py`) that provides a GUI for [Docling](https://github.com/docling-project/docling) document conversion. Users can paste file paths/URLs, drag and drop files, or use native file dialogs to select inputs, then convert to Markdown, HTML, JSON, or DocTags.

## Environment Setup

```bash
# Install all dependencies into .venv (creates it if missing)
uv sync

# Run the application
uv run python main.py
```

- Python version is pinned to **3.12** in `.python-version`.
- Dependencies are managed in `pyproject.toml` via `uv add <package>`.
- Note: the project is named `docling-converter` in `pyproject.toml` to avoid conflicting with the `docling` package.

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | PySide6 GUI application. Single file, entry point. |
| `pyproject.toml` | Project metadata and dependencies. |
| `.python-version` | Python version pin for uv. |
| `README.md` | Human-facing documentation. |
| `AGENTS.md` | This file - agent instructions. |

## Application Architecture

`main.py` is a single-file PySide6 application with these components:

### Classes

- **`MainWindow(QMainWindow)`** - Main application window. Builds the UI layout and handles user interactions.
- **`ConversionWorker(QThread)`** - Background thread that runs docling conversion. Emits `progress` and `finished` signals to update the UI without freezing it.
- **`FileDropTextEdit(QPlainTextEdit)`** - Custom text area that accepts file drag-and-drop. Overrides `dragEnterEvent`, `dragMoveEvent`, and `dropEvent` to append dropped file paths.

### Helper functions

- `_resolve_unique_path(directory, filename)` - Appends `_1`, `_2`, etc. if a file already exists.
- `_get_source_stem(source)` - Extracts a filename stem from a Path or URL.
- `_resolve_sources(raw_text)` - Parses user input text into a list of sources (Paths/URLs) and a list of errors.

### Constants

- `FORMAT_OPTIONS` - Dict mapping display labels to `{"ext": ..., "key": ...}` for each export format.
- `SUPPORTED_EXTENSIONS` - Set of file extensions docling can handle.
- `FILE_FILTER` - Filter string for `QFileDialog.getOpenFileNames`.

### UI Layout (top to bottom)

1. **Input group** - `FileDropTextEdit` (paste/drag paths) + "Browse files..." button (native file dialog)
2. **Output directory** - `QLineEdit` + "Browse..." button (native directory dialog)
3. **Options row** - Format `QComboBox` + filename `QLineEdit`
4. **Action row** - "Convert" `QPushButton` + indeterminate `QProgressBar`
5. **Status label** - Shows per-file progress during conversion
6. **Results/Preview splitter** - `QPlainTextEdit` for results + `QTextEdit` for preview (supports HTML/Markdown rendering)

### Threading model

Conversion runs in `ConversionWorker(QThread)`. The worker:
1. Imports `DocumentConverter` (heavy, done once per worker)
2. Iterates over sources, emitting `progress` signals
3. Emits `finished` with a summary string and the first file's content for preview

The main thread stays responsive during conversion. The Convert button is disabled while a worker is active.

## How to Extend

### Adding a new export format

1. Add an entry to `FORMAT_OPTIONS`:
   ```python
   "My Format (.ext)": {"ext": ".ext", "key": "myformat"},
   ```
2. Add an `elif` branch in `ConversionWorker.run()` for the new key.
3. Handle the new format in `_on_finished()` for preview rendering.

### Adding new input file types

1. Add the extension to `SUPPORTED_EXTENSIONS`.
2. Add it to `FILE_FILTER` for the native file dialog.
3. Verify docling supports the format.

### Splitting into multiple files

If the app grows, consider splitting into:
- `main.py` - entry point
- `converter.py` - `ConversionWorker` and helper functions
- `widgets.py` - `FileDropTextEdit` and other custom widgets
- `constants.py` - `FORMAT_OPTIONS`, `SUPPORTED_EXTENSIONS`, `FILE_FILTER`

## Coding Conventions

- Single-file application for simplicity. Split if it exceeds ~500 lines.
- PySide6 signals/slots for thread-safe UI updates.
- `@Slot()` decorator on all slot methods.
- Docling is imported inside the worker thread to avoid slow startup.
- Use `QFileDialog` for native OS file/directory pickers.
- Validate all user input before starting conversion.

## Version Control

- This project uses **git**.
- The `.venv/` directory and `__pycache__/` are gitignored.
