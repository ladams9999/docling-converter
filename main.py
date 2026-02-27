"""Docling Document Converter - PySide6 GUI application."""

import sys
import tempfile
import warnings
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QUrl, Qt, QThread, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
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
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
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

STATUS_ICON_SUCCESS = "✅"
STATUS_ICON_WARNING = "🟨"
STATUS_ICON_ERROR = "🛑"


# ---------------------------------------------------------------------------
# Worker thread for conversion
# ---------------------------------------------------------------------------


class ConversionWorker(QThread):
    """Runs docling conversion off the main thread."""

    progress = Signal(str)  # status message per file
    result_ready = Signal(object, str)  # (results_payload, first_preview_content)

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
        rows = []
        summary_lines = []
        first_preview = ""

        for i, src in enumerate(self.sources, 1):
            src_label = str(src.resolve()) if isinstance(src, Path) else src
            self.progress.emit(
                f"Converting {i}/{len(self.sources)}: {src_label}..."
            )
            target_name = ""
            severity = "success"
            row_messages: list[str] = []

            try:
                with warnings.catch_warnings(record=True) as captured_warnings:
                    warnings.simplefilter("always")
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
                target_name = out_path.name

                result_status = str(getattr(result, "status", "")).lower()
                result_errors = list(getattr(result, "errors", []) or [])

                if captured_warnings:
                    severity = "warning"
                    row_messages.extend(str(w.message) for w in captured_warnings)

                if result_errors:
                    row_messages.extend(str(item) for item in result_errors)
                    if any(token in result_status for token in ("fail", "fatal", "error")):
                        severity = "error"
                        raise RuntimeError(
                            "; ".join(str(item) for item in result_errors)
                        )
                    severity = "warning"
                elif any(token in result_status for token in ("warn", "partial")):
                    severity = "warning"

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
        self._last_output_dir: Path | None = None
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

        # Browse and Clear buttons in a horizontal layout
        input_btn_layout = QHBoxLayout()
        browse_btn = QPushButton("Browse files...")
        browse_btn.clicked.connect(self._browse_input_files)
        input_btn_layout.addWidget(browse_btn)

        self.clear_input_btn = QPushButton("Clear")
        self.clear_input_btn.clicked.connect(self._clear_input_files)
        input_btn_layout.addWidget(self.clear_input_btn)
        input_layout.addLayout(input_btn_layout)
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

        # --- Status label + open folder button ---
        status_row = QHBoxLayout()
        self.status_label = QLabel("")
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)

        layout.addLayout(status_row)

        output_dir_row = QHBoxLayout()
        self.output_dir_display_label = QLabel("Output directory: (not set)")
        output_dir_row.addWidget(self.output_dir_display_label, stretch=1)

        self.open_folder_btn = QPushButton("Open output directory")
        self.open_folder_btn.setVisible(False)
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        output_dir_row.addWidget(self.open_folder_btn)
        layout.addLayout(output_dir_row)

        # --- Results table ---
        self.results_table = QTableWidget(0, 3)
        self.results_table.setHorizontalHeaderLabels(["Status", "Source", "Target"])
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setWordWrap(False)
        self.results_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.results_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.results_table.setMinimumHeight(120)
        header = self.results_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.setColumnWidth(0, 110)
        self.results_table.setColumnWidth(2, 220)
        layout.addWidget(self.results_table, stretch=1)

        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        self.input_text.textChanged.connect(self._on_sources_changed)
        self.output_dir_edit.textChanged.connect(self._on_output_dir_changed)
        self.filename_edit.textEdited.connect(self._on_filename_edited)
        self._apply_auto_filename()
        self._refresh_output_directory_display()

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

    def _refresh_output_directory_display(self):
        output_dir_text = self.output_dir_edit.text().strip()
        if output_dir_text:
            self.output_dir_display_label.setText(f"Output directory: {output_dir_text}")
        else:
            self.output_dir_display_label.setText("Output directory: (not set)")

    def _populate_results_table(self, rows: list[dict]):
        self.results_table.setRowCount(0)

        for row_data in rows:
            row_idx = self.results_table.rowCount()
            self.results_table.insertRow(row_idx)

            severity = row_data.get("severity", "success")
            icon = _severity_icon(severity)
            label = _severity_label(severity)
            status_item = QTableWidgetItem(f"{icon} {label}")
            source_item = QTableWidgetItem(row_data.get("source", ""))
            target_item = QTableWidgetItem(row_data.get("target", ""))

            messages = row_data.get("messages", [])
            if messages:
                tooltip = "\n".join(messages)
                status_item.setToolTip(tooltip)
                source_item.setToolTip(tooltip)
                target_item.setToolTip(tooltip)

            self.results_table.setItem(row_idx, 0, status_item)
            self.results_table.setItem(row_idx, 1, source_item)
            self.results_table.setItem(row_idx, 2, target_item)

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
    def _clear_input_files(self):
        self.input_text.setPlainText("")

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

    @Slot(str)
    def _on_output_dir_changed(self, _text: str):
        self._refresh_output_directory_display()

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
    def _open_output_folder(self):
        if self._last_output_dir and self._last_output_dir.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_output_dir)))

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
            self.status_label.setText("Validation errors: " + "; ".join(errors))
            self._populate_results_table([])
            return

        # Start worker
        fmt_info = FORMAT_OPTIONS[format_label]
        self.convert_btn.setEnabled(False)
        self.clear_input_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self._populate_results_table([])
        self.open_folder_btn.setVisible(False)
        self.status_label.setStyleSheet("")

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
        self.status_label.setStyleSheet("color: palette(text);")
        self.status_label.setText(message)

    @Slot(object, str)
    def _on_finished(self, payload: dict, preview: str):
        self.progress_bar.setVisible(False)
        self.convert_btn.setEnabled(True)
        self.clear_input_btn.setEnabled(True)

        rows = payload.get("rows", [])
        has_errors = any(row.get("severity") == "error" for row in rows)
        if has_errors:
            self.status_label.setStyleSheet("color: red;")
            self.status_label.setText("Done with errors.")
        else:
            self.status_label.setStyleSheet("color: green;")
            self.status_label.setText("Done.")

        output_dir_text = payload.get("output_dir", "")
        output_dir = Path(output_dir_text) if output_dir_text else None
        if output_dir and output_dir.is_dir():
            self._last_output_dir = output_dir
            self.open_folder_btn.setVisible(True)
        else:
            self._last_output_dir = None

        self._populate_results_table(rows)

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
