# docling-converter

Desktop document converter powered by [Docling](https://github.com/docling-project/docling) and [PySide6](https://doc.qt.io/qtforpython-6/). Convert PDFs, Word docs, PowerPoints, spreadsheets, HTML, images, and more into Markdown, HTML, JSON, or DocTags.

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** package manager

## Setup

```bash
# Clone the repository
git clone <repo-url>
cd docling

# Install dependencies (creates .venv automatically)
uv sync
```

## Usage

Launch the application:

```bash
uv run python main.py
```

The GUI window provides:

1. **Input file(s)** — paste file paths or URLs (one per line), drag and drop files from Explorer, or click **Browse files** to use the native file picker. Pasting a directory path will find all supported files in it.
2. **Output directory** — paste a path or click **Browse** to select.
3. **Export format** — choose from Markdown, HTML, JSON, or DocTags.
4. **Output filename** (optional) — leave blank to auto-generate from the input filename. Duplicate names get a numeric suffix (`report_1.md`, etc.).
5. **Convert** — click to start. Conversion runs in a background thread; progress is shown in the status bar. Results and a preview appear at the bottom.

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

| Format | Extension | Description |
|--------|-----------|-------------|
| Markdown | `.md` | Clean markdown representation |
| HTML | `.html` | HTML export |
| JSON | `.json` | Lossless DoclingDocument JSON |
| DocTags | `.doctags` | Docling document token format |

## Project Structure

```
docling/
  main.py           # PySide6 application (entry point)
  pyproject.toml    # Project config and dependencies
  README.md         # This file
  AGENTS.md         # Instructions for AI agents
  .gitignore        # Git ignore rules
  .python-version   # Python version pin (3.12)
```

## Notes

- Docling downloads AI model weights from Hugging Face on first conversion. This may take a few minutes and requires internet access.
- This project includes `hf-xet` to improve Hugging Face model download performance when Xet-backed storage is available.
- If Xet is unavailable, downloads automatically fall back to regular HTTP.
- PDF conversion is computationally intensive. GPU acceleration is used when available.
- The first import of docling is slow (~10–30s) due to loading PyTorch/Transformers. Subsequent conversions are faster.