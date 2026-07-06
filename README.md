# Docling Converter

Docling Converter is a PySide6 desktop application for converting supported
documents with [Docling](https://github.com/docling-project/docling). It now uses
a workspace-oriented flow with top-level **Settings**, **Workspace**,
**Pending**, and **Converted** tabs. It accepts local file paths, directories,
and HTTP/HTTPS URLs, then exports results to Markdown, HTML, JSON, or DocTags.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Setup

Run these commands from the `docling-converter` repository root.

```bash
git clone <repo-url>
cd docling-converter
uv sync
```

## Run the Application

```bash
uv run python main.py
```

## How to Use It

1. Add one or more sources by pasting paths or URLs, dragging files into the
   Workspace tab input area, or use **Browse files...**.
2. Choose an output directory on the **Workspace** tab, or leave it empty and
   let the app auto-select one from the first writable local source directory
   or your Downloads folder.
3. Save or load a workspace file from the **Workspace** tab when needed.
4. Review and adjust the queued items on the **Pending** tab. You can add files,
   add a directory, add a single URL, remove selected items, or clear the queue.
5. Use the **Settings** tab controls to choose an export format and output
   filename behavior.
6. Start conversion from **Convert** on the Workspace tab or **Convert pending**
   on the Pending tab.
7. Review completed items on the **Converted** tab.

The workspace queue drives conversion. When a queued item converts
successfully, it moves into the converted history and is removed from the
pending list. When a conversion finishes with a valid output directory,
**Open output directory** opens it in the native file explorer.

## Supported Formats

### Input

| Format | Extensions |
|--------|------------|
| PDF | `.pdf` |
| Microsoft Word | `.docx` |
| Microsoft PowerPoint | `.pptx` |
| Microsoft Excel | `.xlsx` |
| HTML | `.html`, `.htm` |
| Images | `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp` |
| LaTeX | `.tex` |
| Markdown | `.md` |

### Output

| Format | Extension |
|--------|-----------|
| Markdown | `.md` |
| HTML | `.html` |
| JSON | `.json` |
| DocTags | `.doctags` |

## Notes

- The default workspace file lives under
  `~/.docling-converter/default-workspace/workspace.json`.
- Docling may download model data on first use, which can take time and
  requires internet access.
- Large PDFs are chunked before conversion when they exceed the configured page
  count or size thresholds.
- Conversion runs in a background thread so the GUI remains responsive.

## Testing

Run the automated test suite with:

```bash
uv run python -m pytest -q
```

See `TEST.md` for the detailed testing guide.

## Documentation

- `AGENTS.md` for contributor and agent guidance
- `IMPLEMENTATION.md` for architecture details
- `PROJECT_PLAN.md` for current project direction
- `PENDING_TASKS.md` and `COMPLETED_TASKS.md` for project tracking
