# Docling Converter

Docling Converter is a PySide6 desktop application for converting supported
documents with [Docling](https://github.com/docling-project/docling). It accepts
local file paths, directories, and HTTP/HTTPS URLs, then exports results to
Markdown, HTML, JSON, or DocTags.

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
   input area, or using **Browse files...**.
2. Choose an output directory, or leave it empty and let the app auto-select
   one from the first writable local source directory or your Downloads folder.
3. Pick an export format.
4. Accept the auto-generated filename or enter your own.
5. Click **Convert**.

The results table shows per-source status, source, and target output. When a
conversion finishes with a valid output directory, **Open output directory**
opens it in the native file explorer.

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

- Docling may download model data on first use, which can take time and
  requires internet access.
- Large PDFs are chunked before conversion when they exceed the configured page
  count or size thresholds.
- Conversion runs in a background thread so the GUI remains responsive.

## Testing

Run the automated test suite with:

```bash
uv run pytest -q
```

See `TEST.md` for the detailed testing guide.

## Documentation

- `AGENTS.md` for contributor and agent guidance
- `IMPLEMENTATION.md` for architecture details
- `PROJECT_PLAN.md` for current project direction
- `PENDING_TASKS.md` and `COMPLETED_TASKS.md` for project tracking
