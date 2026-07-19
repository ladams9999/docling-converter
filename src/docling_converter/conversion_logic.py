"""Conversion worker and helper functions."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import warnings
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PySide6.QtCore import QThread, Signal

FORMAT_OPTIONS = {
    "Markdown (.md)": {"ext": ".md", "key": "markdown"},
    "HTML (.html)": {"ext": ".html", "key": "html"},
    "JSON (.json)": {"ext": ".json", "key": "json"},
    "DocTags (.doctags)": {"ext": ".doctags", "key": "doctags"},
}

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".html",
    ".htm",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
    ".bmp",
    ".tex",
    ".md",
}

FILE_FILTER = (
    "All supported (*.pdf *.docx *.pptx *.xlsx *.html *.htm "
    "*.png *.jpg *.jpeg *.tiff *.tif *.bmp *.tex *.md);;"
    "PDF (*.pdf);;Word (*.docx);;PowerPoint (*.pptx);;"
    "Excel (*.xlsx);;HTML (*.html *.htm);;"
    "Images (*.png *.jpg *.jpeg *.tiff *.tif *.bmp);;"
    "LaTeX (*.tex);;Markdown (*.md);;All files (*)"
)

STATUS_ICON_SUCCESS = "✅"
STATUS_ICON_WARNING = "🟨"
STATUS_ICON_ERROR = "🛑"

PAGE_CHUNK_THRESHOLD = 30
PDF_CHUNK_SIZE = 20
PDF_SIZE_THRESHOLD_MB = 5.0


class ConversionWorker(QThread):
    """Runs docling conversion off the main thread."""

    progress = Signal(str)
    result_ready = Signal(object, str)

    def __init__(
        self,
        sources: list,
        output_dir: Path,
        fmt_info: dict,
        custom_filename: str,
        source_formats: dict[str, str] | None = None,
    ):
        super().__init__()
        self.sources = sources
        self.output_dir = output_dir
        self.fmt_info = fmt_info
        self.custom_filename = custom_filename
        self.source_formats = source_formats or {}

    def run(self):
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        rows = []
        summary_lines = []
        first_preview = ""

        for i, src in enumerate(self.sources, 1):
            src_label = str(src.resolve()) if isinstance(src, Path) else src
            self.progress.emit(f"Converting {i}/{len(self.sources)}: {src_label}...")
            target_name = ""
            severity = "success"
            row_messages: list[str] = []
            temp_files: list[Path] = []
            temp_dirs: list[Path] = []

            try:
                format_label = self.source_formats.get(src_label)
                item_fmt_info = (
                    FORMAT_OPTIONS[format_label]
                    if format_label in FORMAT_OPTIONS
                    else self.fmt_info
                )
                key = item_fmt_info["key"]

                conversion_targets = [src]
                chunked = False
                chunk_reason = ""

                if _is_pdf_source(src):
                    local_pdf = src if isinstance(src, Path) else _download_pdf_url(src)
                    if not isinstance(src, Path):
                        temp_files.append(local_pdf)

                    page_count = _get_pdf_page_count(local_pdf)
                    size_mb = _get_file_size_mb(local_pdf)
                    chunked, chunk_reason = _should_chunk_pdf(page_count, size_mb)

                    if chunked:
                        chunk_paths, chunk_dir = _split_pdf_into_chunks(
                            local_pdf, PDF_CHUNK_SIZE
                        )
                        conversion_targets = chunk_paths
                        temp_dirs.append(chunk_dir)
                        row_messages.append(
                            f"Chunked PDF ({chunk_reason}) into {len(chunk_paths)} chunk(s) of up to {PDF_CHUNK_SIZE} pages."
                        )
                    elif not isinstance(src, Path):
                        conversion_targets = [local_pdf]

                chunk_contents: list[str] = []

                for chunk_index, target in enumerate(conversion_targets, 1):
                    if chunked:
                        self.progress.emit(
                            f"Converting {i}/{len(self.sources)} chunk {chunk_index}/{len(conversion_targets)}: {src_label}..."
                        )

                    with warnings.catch_warnings(record=True) as captured_warnings:
                        warnings.simplefilter("always")
                        result = converter.convert(str(target))

                    chunk_content = _export_document(result.document, key)
                    chunk_contents.append(chunk_content)

                    result_status = str(getattr(result, "status", "")).lower()
                    result_errors = list(getattr(result, "errors", []) or [])

                    if captured_warnings:
                        severity = "warning"
                        row_messages.extend(str(w.message) for w in captured_warnings)

                    if result_errors:
                        row_messages.extend(
                            f"Chunk {chunk_index}: {item}" for item in result_errors
                        )
                        if any(
                            token in result_status for token in ("fail", "fatal", "error")
                        ):
                            severity = "error"
                            raise RuntimeError(
                                "; ".join(str(item) for item in result_errors)
                            )
                        severity = "warning"
                    elif any(token in result_status for token in ("warn", "partial")):
                        severity = "warning"

                content = _combine_chunk_contents(key, chunk_contents)

                if len(self.sources) == 1 and self.custom_filename:
                    fname = self.custom_filename
                else:
                    fname = f"{_get_source_stem(src)}{item_fmt_info['ext']}"

                out_path = _resolve_unique_path(self.output_dir, fname)
                out_path.write_text(content, encoding="utf-8")
                target_name = out_path.name

                rows.append(
                    {
                        "severity": severity,
                        "source": src_label,
                        "target": target_name,
                        "messages": row_messages,
                    }
                )

                icon = _severity_icon(severity)
                summary_lines.append(f"{icon}  {src_label}  ->  {target_name}")

                if not first_preview:
                    first_preview = content

            except Exception as e:
                rows.append(
                    {
                        "severity": "error",
                        "source": src_label,
                        "target": target_name,
                        "messages": [str(e)],
                    }
                )
                icon = _severity_icon("error")
                summary_lines.append(f"{icon}  {src_label}  ->  {target_name} ({e})")
            finally:
                for temp_path in temp_files:
                    try:
                        temp_path.unlink(missing_ok=True)
                    except Exception:
                        pass

                for temp_dir in temp_dirs:
                    shutil.rmtree(temp_dir, ignore_errors=True)

        payload = {
            "rows": rows,
            "summary": "\n".join(summary_lines),
            "has_errors": any(row["severity"] == "error" for row in rows),
            "output_dir": str(self.output_dir),
        }
        self.result_ready.emit(payload, first_preview)


def _severity_icon(severity: str) -> str:
    if severity == "error":
        return STATUS_ICON_ERROR
    if severity == "warning":
        return STATUS_ICON_WARNING
    return STATUS_ICON_SUCCESS


def _severity_label(severity: str) -> str:
    if severity == "error":
        return "Error"
    if severity == "warning":
        return "Warning"
    return "OK"


def _resolve_unique_path(directory: Path, filename: str) -> Path:
    """Append a numeric suffix if the file already exists."""

    target = directory / filename
    if not target.exists():
        return target
    stem = target.stem
    ext = target.suffix
    counter = 1
    while True:
        candidate = directory / f"{stem}_{counter}{ext}"
        if not candidate.exists():
            return candidate
        counter += 1


def _get_source_stem(source) -> str:
    """Extract a filename stem from a path or URL."""

    if isinstance(source, Path):
        return source.stem
    url_path = urlparse(source).path
    return Path(url_path).stem or "document"


def _resolve_sources(raw_text: str) -> tuple[list, list[str]]:
    """Parse raw text into a list of sources and a list of errors."""

    sources = []
    errors = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("http://") or line.startswith("https://"):
            sources.append(line)
        else:
            p = Path(line)
            if p.is_file():
                sources.append(p)
            elif p.is_dir():
                children = [
                    c
                    for c in sorted(p.iterdir())
                    if c.suffix.lower() in SUPPORTED_EXTENSIONS
                ]
                if children:
                    sources.extend(children)
                else:
                    errors.append(f"No supported files in directory: {p}")
            else:
                errors.append(f"File not found: {line}")
    return sources, errors


def _is_writable_directory(directory: Path) -> bool:
    """Return True if directory exists and is writable."""

    if not directory.is_dir():
        return False

    try:
        with tempfile.NamedTemporaryFile(dir=directory, delete=True):
            pass
        return True
    except Exception:
        return False


def _get_downloads_directory() -> Path:
    """Best-effort resolve user's downloads directory."""

    downloads = Path.home() / "Downloads"
    if downloads.exists():
        return downloads

    try:
        downloads.mkdir(parents=True, exist_ok=True)
        return downloads
    except Exception:
        return Path.home()


def _resolve_auto_output_directory(sources: list) -> Path:
    """Pick output dir from first local source if writable, else Downloads."""

    fallback = _get_downloads_directory()

    for source in sources:
        if isinstance(source, Path):
            candidate = source.parent
            if _is_writable_directory(candidate):
                return candidate
            return fallback

    return fallback


def _is_pdf_source(source) -> bool:
    if isinstance(source, Path):
        return source.suffix.lower() == ".pdf"
    parsed = urlparse(source)
    return parsed.path.lower().endswith(".pdf")


def _download_pdf_url(url: str) -> Path:
    request = Request(url, headers={"User-Agent": "docling-converter/1.0"})
    with urlopen(request, timeout=60) as response:
        data = response.read()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(data)
        return Path(temp_file.name)


def _get_pdf_page_count(pdf_path: Path) -> int:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return len(reader.pages)


def _get_file_size_mb(file_path: Path) -> float:
    return file_path.stat().st_size / (1024 * 1024)


def _should_chunk_pdf(page_count: int, size_mb: float) -> tuple[bool, str]:
    if page_count > PAGE_CHUNK_THRESHOLD:
        return True, f"page count {page_count} > {PAGE_CHUNK_THRESHOLD}"
    if size_mb > PDF_SIZE_THRESHOLD_MB:
        return True, f"size {size_mb:.1f} MB > {PDF_SIZE_THRESHOLD_MB:.1f} MB"
    return False, ""


def _split_pdf_into_chunks(pdf_path: Path, chunk_size: int) -> tuple[list[Path], Path]:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(pdf_path))
    chunk_dir = Path(tempfile.mkdtemp(prefix="docling_chunks_"))
    chunk_paths: list[Path] = []

    for start in range(0, len(reader.pages), chunk_size):
        end = min(start + chunk_size, len(reader.pages))
        writer = PdfWriter()
        for page_index in range(start, end):
            writer.add_page(reader.pages[page_index])

        chunk_path = chunk_dir / f"{pdf_path.stem}_p{start + 1}_{end}.pdf"
        with chunk_path.open("wb") as chunk_file:
            writer.write(chunk_file)
        chunk_paths.append(chunk_path)

    return chunk_paths, chunk_dir


def _export_document(doc, key: str) -> str:
    if key == "markdown":
        return doc.export_to_markdown()
    if key == "html":
        return doc.export_to_html()
    if key == "json":
        return doc.model_dump_json(indent=2)
    if key == "doctags":
        return doc.export_to_doctags()
    return doc.export_to_markdown()


def _extract_html_body(html: str) -> str:
    body_match = re.search(r"<body[^>]*>(.*?)</body>", html, flags=re.IGNORECASE | re.DOTALL)
    if body_match:
        return body_match.group(1).strip()
    return html.strip()


def _merge_json_values(base, incoming):
    if isinstance(base, dict) and isinstance(incoming, dict):
        merged = dict(base)
        for key, value in incoming.items():
            if key in merged:
                merged[key] = _merge_json_values(merged[key], value)
            else:
                merged[key] = value
        return merged

    if isinstance(base, list) and isinstance(incoming, list):
        return base + incoming

    if base == incoming:
        return base

    return incoming


def _combine_chunk_contents(key: str, chunk_contents: list[str]) -> str:
    if not chunk_contents:
        return ""

    if len(chunk_contents) == 1:
        return chunk_contents[0]

    if key == "markdown":
        return "\n\n".join(chunk_contents)

    if key == "html":
        body_sections = [f"<section>{_extract_html_body(part)}</section>" for part in chunk_contents]
        body = "\n".join(body_sections)
        return f"<!DOCTYPE html><html><body>{body}</body></html>"

    if key == "json":
        parsed_docs = [json.loads(part) for part in chunk_contents]
        merged_doc = parsed_docs[0]
        for next_doc in parsed_docs[1:]:
            merged_doc = _merge_json_values(merged_doc, next_doc)
        return json.dumps(merged_doc, indent=2)

    return "\n\n".join(chunk_contents)
