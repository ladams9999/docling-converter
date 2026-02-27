"""Docling Document Converter - PySide6 GUI application."""

import sys
import tempfile
from html import escape
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FORMAT_OPTIONS = {
    "Markdown (.md)": {"ext": ".md", "key": "markdown"},
    "HTML (.html)": {"ext": ".html", "key": "html"},
    "JSON (.json)": {"ext": ".json", "key": "json"},
    "DocTags (.doctags)": {"ext": ".doctags", "key": "doctags"},
}

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx",
    ".html", ".htm",
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp",
    ".tex", ".md",
}

FILE_FILTER = (
    "All supported (*.pdf *.docx *.pptx *.xlsx *.html *.htm "
    "*.png *.jpg *.jpeg *.tiff *.tif *.bmp *.tex *.md);;"
    "PDF (*.pdf);;Word (*.docx);;PowerPoint (*.pptx);;"
    "Excel (*.xlsx);;HTML (*.html *.htm);;"
    "Images (*.png *.jpg *.jpeg *.tiff *.tif *.bmp);;"
    "LaTeX (*.tex);;Markdown (*.md);;All files (*)"
)


# ---------------------------------------------------------------------------
# Worker thread for conversion
# ---------------------------------------------------------------------------


class ConversionWorker(QThread):
    """Runs docling conversion off the main thread."""

    progress = Signal(str)  # status message per file
    result_ready = Signal(str, str)  # (results_summary, first_preview_content)

    def __init__(
        self,
        sources: list,
        output_dir: Path,
        fmt_info: dict,
        custom_filename: str,
    ):
        super().__init__()
        self.sources = sources
        self.output_dir = output_dir
        self.fmt_info = fmt_info
        self.custom_filename = custom_filename

    def run(self):
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        results = []
        first_preview = ""

        for i, src in enumerate(self.sources, 1):
            src_label = Path(src).name if isinstance(src, Path) else src
            self.progress.emit(
                f"Converting {i}/{len(self.sources)}: {src_label}..."
            )
            try:
                result = converter.convert(str(src))
                doc = result.document

                key = self.fmt_info["key"]
                if key == "markdown":
                    content = doc.export_to_markdown()
                elif key == "html":
                    content = doc.export_to_html()
                elif key == "json":
                    content = doc.model_dump_json(indent=2)
                elif key == "doctags":
                    content = doc.export_to_doctags()
                else:
                    content = doc.export_to_markdown()

                # Determine filename
                if len(self.sources) == 1 and self.custom_filename:
                    fname = self.custom_filename
                else:
                    fname = f"{_get_source_stem(src)}{self.fmt_info['ext']}"

                out_path = _resolve_unique_path(self.output_dir, fname)
                out_path.write_text(content, encoding="utf-8")

                results.append(f"  {src_label}  ->  {out_path.name}")

                if not first_preview:
                    first_preview = content

            except Exception as e:
                results.append(f"  ERROR  {src_label}: {e}")

        summary = (
            f"Output directory: {self.output_dir}\n\n"
            + "\n".join(results)
        )
        self.result_ready.emit(summary, first_preview)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
                    c for c in sorted(p.iterdir())
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


# ---------------------------------------------------------------------------
# Drop-enabled text area
# ---------------------------------------------------------------------------


class FileDropTextEdit(QPlainTextEdit):
    """QPlainTextEdit that accepts file drops and appends their paths."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = []
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    paths.append(url.toLocalFile())
                else:
                    paths.append(url.toString())
            current = self.toPlainText().rstrip()
            separator = "\n" if current else ""
            self.setPlainText(current + separator + "\n".join(paths))
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Docling Document Converter")
        self.setMinimumSize(700, 600)
        self._worker = None
        self._auto_filename_enabled = True
        self._last_auto_filename = ""
        self._updating_filename = False
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Input files ---
        input_group = QGroupBox("Input file(s) — paste paths/URLs or drag && drop files")
        input_layout = QVBoxLayout(input_group)

        self.input_text = FileDropTextEdit()
        self.input_text.setPlaceholderText(
            "Paste file paths or URLs, one per line.\n"
            "You can also drag and drop files here.\n\n"
            "Examples:\n"
            "  C:\\docs\\report.pdf\n"
            "  https://arxiv.org/pdf/2408.09869"
        )
        self.input_text.setMaximumHeight(120)
        input_layout.addWidget(self.input_text)

        browse_btn = QPushButton("Browse files...")
        browse_btn.clicked.connect(self._browse_input_files)
        input_layout.addWidget(browse_btn)
        layout.addWidget(input_group)

        # --- Output directory ---
        output_group = QGroupBox("Output directory")
        output_layout = QHBoxLayout(output_group)

        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("C:\\docs\\output")
        output_layout.addWidget(self.output_dir_edit)

        browse_dir_btn = QPushButton("Browse...")
        browse_dir_btn.clicked.connect(self._browse_output_dir)
        output_layout.addWidget(browse_dir_btn)
        layout.addWidget(output_group)

        # --- Format + filename row ---
        options_layout = QHBoxLayout()

        fmt_group = QGroupBox("Export format")
        fmt_inner = QVBoxLayout(fmt_group)
        self.format_combo = QComboBox()
        self.format_combo.addItems(list(FORMAT_OPTIONS.keys()))
        fmt_inner.addWidget(self.format_combo)
        options_layout.addWidget(fmt_group)

        fname_group = QGroupBox("Output filename")
        fname_inner = QVBoxLayout(fname_group)
        fname_row = QHBoxLayout()
        self.filename_edit = QLineEdit()
        fname_row.addWidget(self.filename_edit)
        self.auto_filename_btn = QPushButton("Auto")
        self.auto_filename_btn.clicked.connect(self._on_auto_filename_clicked)
        fname_row.addWidget(self.auto_filename_btn)
        fname_inner.addLayout(fname_row)
        options_layout.addWidget(fname_group)

        layout.addLayout(options_layout)

        # --- Convert button + progress ---
        action_layout = QHBoxLayout()
        self.convert_btn = QPushButton("Convert")
        self.convert_btn.setMinimumHeight(36)
        self.convert_btn.clicked.connect(self._start_conversion)
        action_layout.addWidget(self.convert_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.setVisible(False)
        action_layout.addWidget(self.progress_bar)
        layout.addLayout(action_layout)

        # --- Status label ---
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # --- Results + Preview splitter ---
        splitter = QSplitter(Qt.Orientation.Vertical)

        self.results_text = QTextBrowser()
        self.results_text.setReadOnly(True)
        self.results_text.setOpenExternalLinks(True)
        self.results_text.setPlaceholderText("Conversion results will appear here.")
        splitter.addWidget(self.results_text)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Preview of converted content.")
        splitter.addWidget(self.preview_text)

        splitter.setSizes([150, 300])
        layout.addWidget(splitter, stretch=1)

        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        self.input_text.textChanged.connect(self._on_sources_changed)
        self.filename_edit.textEdited.connect(self._on_filename_edited)
        self._apply_auto_filename()

    def _get_default_output_filename(self) -> str:
        format_label = self.format_combo.currentText()
        ext = FORMAT_OPTIONS[format_label]["ext"]
        raw = self.input_text.toPlainText().strip()

        if raw:
            sources, _ = _resolve_sources(raw)
            if sources:
                return f"{_get_source_stem(sources[0])}{ext}"

            first_line = next((line.strip() for line in raw.splitlines() if line.strip()), "")
            if first_line:
                if first_line.startswith("http://") or first_line.startswith("https://"):
                    stem = _get_source_stem(first_line)
                else:
                    stem = Path(first_line).stem or "document"
                return f"{stem}{ext}"

        return f"document{ext}"

    def _apply_auto_filename(self):
        filename = self._get_default_output_filename()
        self._last_auto_filename = filename
        self._updating_filename = True
        self.filename_edit.setText(filename)
        self._updating_filename = False

    def _update_auto_filename(self):
        filename = self._get_default_output_filename()
        self._last_auto_filename = filename
        if self._auto_filename_enabled or not self.filename_edit.text().strip():
            self._auto_filename_enabled = True
            self._updating_filename = True
            self.filename_edit.setText(filename)
            self._updating_filename = False

    def _set_results_text(self, text: str, output_dir: Path | None = None):
        if output_dir is None:
            self.results_text.setPlainText(text)
            return

        escaped = escape(text).replace("\n", "<br>")
        output_uri = output_dir.resolve().as_uri()
        link = f'<br><br><a href="{output_uri}">Open output directory</a>'
        self.results_text.setHtml(escaped + link)

    # --- Slots ---

    @Slot()
    def _browse_input_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select input file(s)", "", FILE_FILTER
        )
        if files:
            current = self.input_text.toPlainText().rstrip()
            separator = "\n" if current else ""
            self.input_text.setPlainText(
                current + separator + "\n".join(files)
            )

    @Slot()
    def _browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select output directory"
        )
        if directory:
            self.output_dir_edit.setText(directory)

    @Slot(str)
    def _on_format_changed(self, _text: str):
        self._update_auto_filename()

    @Slot()
    def _on_sources_changed(self):
        self._update_auto_filename()

        if self.output_dir_edit.text().strip():
            return

        raw = self.input_text.toPlainText().strip()
        if not raw:
            return

        sources, _ = _resolve_sources(raw)
        if not sources:
            return

        output_dir = _resolve_auto_output_directory(sources)
        self.output_dir_edit.setText(str(output_dir))
        self._set_results_text(f"Output directory: {output_dir}", output_dir)

    @Slot(str)
    def _on_filename_edited(self, text: str):
        if self._updating_filename:
            return

        if not text.strip():
            self._auto_filename_enabled = True
            self._apply_auto_filename()
            return

        self._auto_filename_enabled = False

    @Slot()
    def _on_auto_filename_clicked(self):
        self._auto_filename_enabled = True
        self._apply_auto_filename()

    @Slot()
    def _start_conversion(self):
        raw = self.input_text.toPlainText().strip()
        output_dir_str = self.output_dir_edit.text().strip()
        format_label = self.format_combo.currentText()
        custom_filename = self.filename_edit.text().strip()

        # Validate
        errors = []
        if not raw:
            errors.append("No input files specified.")
        if not output_dir_str:
            errors.append("No output directory specified.")

        output_dir = Path(output_dir_str) if output_dir_str else None
        if not output_dir or not output_dir.is_dir():
            errors.append(f"Output directory does not exist: {output_dir_str}")

        sources, resolve_errors = _resolve_sources(raw) if raw else ([], [])
        errors.extend(resolve_errors)

        if not sources and not errors:
            errors.append("No valid input files resolved.")

        if errors:
            self._set_results_text(
                "Validation errors:\n\n" + "\n".join(f"  - {e}" for e in errors)
            )
            return

        # Start worker
        fmt_info = FORMAT_OPTIONS[format_label]
        self.convert_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.results_text.clear()
        self.preview_text.clear()

        assert output_dir is not None  # guaranteed by validation above
        self._worker = ConversionWorker(
            sources, output_dir, fmt_info, custom_filename
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.result_ready.connect(self._on_finished)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    @Slot(str)
    def _on_progress(self, message: str):
        self.status_label.setText(message)

    @Slot(str, str)
    def _on_finished(self, summary: str, preview: str):
        self.progress_bar.setVisible(False)
        self.convert_btn.setEnabled(True)
        self.status_label.setText("Done.")

        output_dir_text = self.output_dir_edit.text().strip()
        output_dir = Path(output_dir_text) if output_dir_text else None
        if output_dir and output_dir.is_dir():
            self._set_results_text(summary, output_dir)
        else:
            self._set_results_text(summary)

        fmt_key = FORMAT_OPTIONS[self.format_combo.currentText()]["key"]
        if fmt_key == "html":
            self.preview_text.setHtml(preview[:50000])
        elif fmt_key == "markdown":
            self.preview_text.setMarkdown(preview[:50000])
        else:
            self.preview_text.setPlainText(preview[:50000])

    @Slot()
    def _on_worker_finished(self):
        self._worker = None

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.wait(5000)
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
