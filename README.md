# Docling Converter

Docling Converter is a PySide6 desktop application for converting supported
documents with [Docling](https://github.com/docling-project/docling). It now uses
a workspace-oriented flow with top-level **Settings**, **Workspace**,
**Pending**, and **Converted** tabs. It accepts local file paths, directories,
HTTP/HTTPS URLs, and public wiki-like sites, then exports results to Markdown,
HTML, JSON, or DocTags.

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
uv run docling-converter
```

## How to Use It

Tabs split by scope: **Settings** holds app-wide preferences that apply
regardless of which workspace is open; **Workspace** holds everything scoped
to the current workspace (identity, default format, VLM config, output
filename); **Pending** is where you choose what to convert; **Converted** is
where output went and what has completed.

1. Set the workspace base directory on **Settings** — this is the one
   app-wide preference, independent of any single workspace.
2. On **Workspace**, use **New workspace...** to choose a label, output
   directory, and workspace filename, or **Load workspace...** to reopen an
   existing one. Set the workspace label, default export format, VLM picture
   description, and output filename here — all of it is saved with the
   workspace file.
3. On **Pending**, add sources by pasting paths/URLs, dragging files into the
   input area, or using **Browse files...**/**Add files...**/**Add
   directory...**/**Add URL**/**Add wiki...**. Review and adjust the queue —
   per-file format overrides, remove selected items, or clear the queue.
4. Start conversion with **Convert pending** on the **Pending** tab.
5. On **Converted**, set (or confirm) the output directory — leave it empty
   and it auto-fills from the first writable local source directory or your
   Downloads folder. Review the planned Output files list, and after
   conversion, the full converted history: rows from the most recent run are
   highlighted, click **Open output directory** to jump to the result.

## Picture Description (VLM)

On the **Workspace** tab, enable "Describe pictures during conversion" to
have a vision-language model caption pictures found in PDF and image sources
during conversion — this is per-workspace, so different workspaces can use
different models or have it off entirely. Configure any OpenAI-compatible
chat-completions endpoint:

- **API URL** — defaults to a local Ollama server
  (`http://localhost:11434/v1/chat/completions`).
- **Model** — the model tag to request (defaults to `granite3.2-vision:2b`;
  any vision-capable Ollama model works, e.g. `qwen2.5vl`, `llava`).
- **API key** — optional, only needed for a hosted API that requires one.
  Saved in plaintext in the workspace JSON file — avoid entering a long-lived
  key here if you share or version-control your workspace files.

Switching providers/models is a Settings change, not a code change.

The workspace queue drives conversion. When a queued item converts
successfully, it moves into the converted history and is removed from the
pending list. When a conversion finishes with a valid output directory,
**Open output directory** opens it in the native file explorer.

### Import a Wiki

1. Click **Add wiki...** on the **Pending** tab and enter any page in a public,
   authentication-free wiki-like site.
2. Choose **Whole wiki** or **Sub-wiki**, review the inferred root, and choose
   whether to respect `robots.txt` and download linked assets.
3. Confirm a root that differs from the starting page, then monitor or cancel
   background discovery.
4. Remove pages you do not want from **Pending** and select Markdown or HTML.
5. Convert the queue. Wiki files use flattened path-based names in one output
   directory, and links between successful pages are rewritten locally.

**Whole wiki** follows eligible links recursively under the confirmed root.
**Sub-wiki** always includes the starting page, recursively follows linked pages
in child directories, and includes one level of pages linked in the starting
page's directory. URL fragments identify headings, not separate pages.

Discovery snapshots pages under `~/.docling-converter/cache/wiki/`. Markdown
outputs start with YAML provenance containing `original_url` and `fetched_at`;
HTML outputs contain the same values in a leading comment. If assets are
enabled, they are copied to an `assets` directory. Existing output conflicts are
listed for confirmation before wiki files are overwritten.

For example, a page at `a/subject/page.html` becomes
`a-subject-page.md` or `a-subject-page.html`. Links to excluded, failed, or
external pages remain absolute web URLs.

## Supported Formats

### Input

| Format | Extensions |
| ------ | ---------- |
| PDF | `.pdf` |
| Microsoft Word | `.docx` |
| Microsoft PowerPoint | `.pptx` |
| Microsoft Excel | `.xlsx` |
| HTML | `.html`, `.htm` |
| Images | `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp` |
| LaTeX | `.tex` |
| Markdown | `.md` |
| EPUB | `.epub` |
| Plain text | `.txt` |

### Output

| Format | Extension |
| ------ | --------- |
| Markdown | `.md` |
| HTML | `.html` |
| JSON | `.json` |
| DocTags | `.doctags` |

## Notes

- The default workspace file lives under
  `~/.docling-converter/default-workspace/workspace.json`.
- The default base directory for new workspaces is
  `~/.docling-converter/workspaces` and can be changed on **Settings**.
- Docling may download model data on first use, which can take time and
  requires internet access.
- Picture description requires the configured endpoint (a local Ollama server
  by default) to already be running with the model pulled. If the endpoint is
  unreachable, conversion still succeeds — pictures are just left without a
  caption, with no error surfaced in the results table.
- Large PDFs are chunked before conversion when they exceed the configured page
  count or size thresholds.
- Conversion runs in a background thread so the GUI remains responsive.
- Wiki batches currently support Markdown and HTML. Convert wiki pages separately
  from ordinary queued sources.
- Wiki discovery has no page-count limit; use the live count and
  **Cancel discovery** when needed. Request, response, and asset-size safeguards
  still apply.
- Authentication, browser cookies, localhost, and private-network wiki targets
  are not supported.

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
