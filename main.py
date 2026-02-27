"""Docling Document Converter - PySide6 GUI application."""

import sys
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
                    content = doc.export_to_document_tokens()
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
        self.format_combo.addItems(FORMAT_OPTIONS.keys())
        fmt_inner.addWidget(self.format_combo)
        options_layout.addWidget(fmt_group)

        fname_group = QGroupBox("Output filename (blank = auto)")
        fname_inner = QVBoxLayout(fname_group)
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("(auto-generated from input)")
        fname_inner.addWidget(self.filename_edit)
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
        splitter = QSplitter(Qt.Vertical)

        self.results_text = QPlainTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setPlaceholderText("Conversion results will appear here.")
        splitter.addWidget(self.results_text)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Preview of converted content.")
        splitter.addWidget(self.preview_text)

        splitter.setSizes([150, 300])
        layout.addWidget(splitter, stretch=1)

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
        if output_dir and not output_dir.is_dir():
            errors.append(f"Output directory does not exist: {output_dir}")

        sources, resolve_errors = _resolve_sources(raw) if raw else ([], [])
        errors.extend(resolve_errors)

        if not sources and not errors:
            errors.append("No valid input files resolved.")

        if errors:
            self.results_text.setPlainText(
                "Validation errors:\n\n" + "\n".join(f"  - {e}" for e in errors)
            )
            return

        # Start worker
        fmt_info = FORMAT_OPTIONS[format_label]
        self.convert_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.results_text.clear()
        self.preview_text.clear()

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
        self.results_text.setPlainText(summary)

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
