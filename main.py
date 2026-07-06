"""Docling Document Converter - PySide6 GUI application."""

import sys
from pathlib import Path

from PySide6.QtCore import QUrl, Qt, Slot
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
    QListWidget,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QHeaderView,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
import conversion_logic as _conversion_logic
from conversion_logic import (
    FILE_FILTER,
    FORMAT_OPTIONS,
    _combine_chunk_contents,
    _download_pdf_url,
    _export_document,
    _extract_html_body,
    _get_downloads_directory,
    _get_file_size_mb,
    _get_pdf_page_count,
    _get_source_stem,
    _is_pdf_source,
    _is_writable_directory,
    _merge_json_values,
    _resolve_auto_output_directory,
    _resolve_sources,
    _resolve_unique_path,
    _severity_icon,
    _severity_label,
    _should_chunk_pdf,
    _split_pdf_into_chunks,
)
from workspace_model import ConvertedItem, WorkspaceData, WorkspaceSettings
from workspace_paths import get_default_workspace_file
from workspace_persistence import load_workspace, save_workspace


def _sync_conversion_logic_bindings():
    _conversion_logic._download_pdf_url = _download_pdf_url
    _conversion_logic._export_document = _export_document
    _conversion_logic._get_downloads_directory = _get_downloads_directory
    _conversion_logic._get_file_size_mb = _get_file_size_mb
    _conversion_logic._get_pdf_page_count = _get_pdf_page_count
    _conversion_logic._get_source_stem = _get_source_stem
    _conversion_logic._is_pdf_source = _is_pdf_source
    _conversion_logic._is_writable_directory = _is_writable_directory
    _conversion_logic._resolve_unique_path = _resolve_unique_path
    _conversion_logic._severity_icon = _severity_icon
    _conversion_logic._should_chunk_pdf = _should_chunk_pdf
    _conversion_logic._split_pdf_into_chunks = _split_pdf_into_chunks


class ConversionWorker(_conversion_logic.ConversionWorker):
    def run(self):
        _sync_conversion_logic_bindings()
        super().run()


def _resolve_auto_output_directory(sources: list) -> Path:
    _sync_conversion_logic_bindings()
    return _conversion_logic._resolve_auto_output_directory(sources)


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
        self._applying_workspace = False
        self._last_output_dir: Path | None = None
        self._workspace_path = get_default_workspace_file()
        self._workspace = WorkspaceData()
        self._build_ui()
        self._sync_workspace_from_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        self.tabs = QTabWidget()
        root_layout.addWidget(self.tabs)

        self.settings_tab = QWidget()
        self.workspace_tab = QWidget()
        self.pending_tab = QWidget()
        self.converted_tab = QWidget()

        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.workspace_tab, "Workspace")
        self.tabs.addTab(self.pending_tab, "Pending")
        self.tabs.addTab(self.converted_tab, "Converted")

        self.settings_layout = QVBoxLayout(self.settings_tab)
        self.settings_layout.addWidget(
            QLabel("Workspace settings and conversion options will appear here.")
        )
        self.settings_layout.addStretch(1)

        self.pending_layout = QVBoxLayout(self.pending_tab)
        pending_progress_group = QGroupBox("Processing")
        pending_progress_layout = QVBoxLayout(pending_progress_group)
        self.pending_status_label = QLabel("")
        pending_progress_layout.addWidget(self.pending_status_label)
        self.pending_progress_bar = QProgressBar()
        self.pending_progress_bar.setRange(0, 0)
        self.pending_progress_bar.setVisible(False)
        pending_progress_layout.addWidget(self.pending_progress_bar)
        self.pending_layout.addWidget(pending_progress_group)

        pending_controls_layout = QHBoxLayout()

        self.pending_add_files_btn = QPushButton("Add files...")
        self.pending_add_files_btn.clicked.connect(self._add_pending_files_from_dialog)
        pending_controls_layout.addWidget(self.pending_add_files_btn)

        self.pending_add_directory_btn = QPushButton("Add directory...")
        self.pending_add_directory_btn.clicked.connect(
            self._add_pending_directory_from_dialog
        )
        pending_controls_layout.addWidget(self.pending_add_directory_btn)

        self.pending_url_edit = QLineEdit()
        self.pending_url_edit.setPlaceholderText("https://example.com/page")
        pending_controls_layout.addWidget(self.pending_url_edit, stretch=1)

        self.pending_add_url_btn = QPushButton("Add URL")
        self.pending_add_url_btn.clicked.connect(self._add_pending_url)
        pending_controls_layout.addWidget(self.pending_add_url_btn)
        self.pending_layout.addLayout(pending_controls_layout)

        self.pending_list = QListWidget()
        self.pending_layout.addWidget(self.pending_list, stretch=1)

        pending_actions_layout = QHBoxLayout()
        self.pending_remove_btn = QPushButton("Remove selected")
        self.pending_remove_btn.clicked.connect(self._remove_selected_pending_sources)
        pending_actions_layout.addWidget(self.pending_remove_btn)

        self.pending_clear_btn = QPushButton("Clear pending")
        self.pending_clear_btn.clicked.connect(self._clear_pending_sources)
        pending_actions_layout.addWidget(self.pending_clear_btn)
        pending_actions_layout.addStretch(1)
        self.pending_layout.addLayout(pending_actions_layout)

        self.converted_layout = QVBoxLayout(self.converted_tab)
        converted_progress_group = QGroupBox("Processing")
        converted_progress_layout = QVBoxLayout(converted_progress_group)
        self.converted_status_label = QLabel("")
        converted_progress_layout.addWidget(self.converted_status_label)
        self.converted_progress_bar = QProgressBar()
        self.converted_progress_bar.setRange(0, 0)
        self.converted_progress_bar.setVisible(False)
        converted_progress_layout.addWidget(self.converted_progress_bar)
        self.converted_layout.addWidget(converted_progress_group)

        self.converted_table = QTableWidget(0, 3)
        self.converted_table.setHorizontalHeaderLabels(["Status", "Source", "Target"])
        self.converted_table.verticalHeader().setVisible(False)
        self.converted_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.converted_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.converted_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.converted_table.setAlternatingRowColors(True)
        self.converted_table.setWordWrap(False)
        self.converted_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.converted_table.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.converted_table.setMinimumHeight(160)
        converted_header = self.converted_table.horizontalHeader()
        converted_header.setStretchLastSection(False)
        converted_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        converted_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        converted_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.converted_table.setColumnWidth(0, 110)
        self.converted_table.setColumnWidth(2, 220)
        self.converted_layout.addWidget(self.converted_table, stretch=1)

        layout = QVBoxLayout(self.workspace_tab)

        workspace_actions_group = QGroupBox("Workspace file")
        workspace_actions_layout = QHBoxLayout(workspace_actions_group)
        self.workspace_path_label = QLabel("")
        workspace_actions_layout.addWidget(self.workspace_path_label, stretch=1)

        self.load_workspace_btn = QPushButton("Load workspace...")
        self.load_workspace_btn.clicked.connect(self._load_workspace_from_dialog)
        workspace_actions_layout.addWidget(self.load_workspace_btn)

        self.save_workspace_btn = QPushButton("Save workspace...")
        self.save_workspace_btn.clicked.connect(self._save_workspace_from_dialog)
        workspace_actions_layout.addWidget(self.save_workspace_btn)
        layout.addWidget(workspace_actions_group)

        # --- Input files ---
        input_group = QGroupBox(
            "Input file(s) — paste paths/URLs or drag && drop files"
        )
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
        self.results_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.results_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setWordWrap(False)
        self.results_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.results_table.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
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
        self._refresh_workspace_path_display()

    def _refresh_workspace_path_display(self):
        self.workspace_path_label.setText(f"Workspace file: {self._workspace_path}")

    def _set_status_message(
        self,
        message: str,
        *,
        busy: bool = False,
        style: str = "color: palette(text);",
    ):
        self.status_label.setStyleSheet(style)
        self.status_label.setText(message)
        self.progress_bar.setVisible(busy)

        for label, bar in (
            (self.pending_status_label, self.pending_progress_bar),
            (self.converted_status_label, self.converted_progress_bar),
        ):
            label.setStyleSheet(style)
            label.setText(message)
            bar.setVisible(busy)

    def _current_workspace_settings(self) -> WorkspaceSettings:
        return WorkspaceSettings(
            format_label=self.format_combo.currentText(),
            custom_filename=self.filename_edit.text().strip(),
            auto_filename_enabled=self._auto_filename_enabled,
        )

    def _resolved_workspace_sources(self) -> list[str]:
        raw = self.input_text.toPlainText().strip()
        if not raw:
            return []

        sources, _ = _resolve_sources(raw)
        if sources:
            return [
                str(source.resolve()) if isinstance(source, Path) else source
                for source in sources
            ]

        return [line.strip() for line in raw.splitlines() if line.strip()]

    def _sync_workspace_from_ui(self):
        if self._applying_workspace:
            return
        self._workspace.target_dir = self.output_dir_edit.text().strip()
        self._workspace.pending_sources = self._resolved_workspace_sources()
        self._workspace.settings = self._current_workspace_settings()
        self._refresh_pending_list()
        self._refresh_converted_table()

    def _refresh_pending_list(self):
        self.pending_list.clear()
        self.pending_list.addItems(self._workspace.pending_sources)

    def _refresh_converted_table(self):
        rows = [item.to_dict() for item in self._workspace.converted_items]
        self.converted_table.setRowCount(0)

        for row_data in rows:
            row_idx = self.converted_table.rowCount()
            self.converted_table.insertRow(row_idx)

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

            self.converted_table.setItem(row_idx, 0, status_item)
            self.converted_table.setItem(row_idx, 1, source_item)
            self.converted_table.setItem(row_idx, 2, target_item)

    def _set_pending_sources(self, sources: list[str]):
        self._applying_workspace = True
        try:
            self._workspace.pending_sources = list(sources)
            self.input_text.setPlainText("\n".join(self._workspace.pending_sources))
        finally:
            self._applying_workspace = False
        self._sync_workspace_from_ui()

    def _append_pending_sources(self, entries: list[str]):
        raw = "\n".join(entries)
        sources, errors = _resolve_sources(raw)
        normalized_sources = [
            str(source.resolve()) if isinstance(source, Path) else source
            for source in sources
        ]
        if errors:
            self._set_status_message(
                "Pending-source errors: " + "; ".join(errors),
                style="color: red;",
            )
        if not normalized_sources:
            return

        merged_sources = list(self._workspace.pending_sources)
        for source in normalized_sources:
            if source not in merged_sources:
                merged_sources.append(source)
        self._set_pending_sources(merged_sources)
        self._set_status_message(f"Queued {len(normalized_sources)} source(s).")

    def _apply_workspace_to_ui(self, workspace: WorkspaceData):
        self._applying_workspace = True
        try:
            self._workspace = workspace

            self.output_dir_edit.setText(workspace.target_dir)
            self.input_text.setPlainText("\n".join(workspace.pending_sources))

            self.format_combo.setCurrentText(workspace.settings.format_label)
            self._auto_filename_enabled = workspace.settings.auto_filename_enabled

            if workspace.settings.auto_filename_enabled:
                self._apply_auto_filename()
            else:
                self._updating_filename = True
                self.filename_edit.setText(workspace.settings.custom_filename)
                self._updating_filename = False

            self._refresh_output_directory_display()
        finally:
            self._applying_workspace = False
        self._sync_workspace_from_ui()

    def _save_workspace_to_path(self, path: Path):
        self._sync_workspace_from_ui()
        save_workspace(self._workspace, path)
        self._workspace_path = path
        self._refresh_workspace_path_display()
        self._set_status_message(f"Saved workspace: {path}")

    def _load_workspace_to_path(self, path: Path):
        workspace = load_workspace(path)
        self._workspace_path = path
        self._refresh_workspace_path_display()
        self._apply_workspace_to_ui(workspace)
        self._set_status_message(f"Loaded workspace: {path}")

    def _get_default_output_filename(self) -> str:
        format_label = self.format_combo.currentText()
        ext = FORMAT_OPTIONS[format_label]["ext"]
        raw = self.input_text.toPlainText().strip()

        if raw:
            sources, _ = _resolve_sources(raw)
            if sources:
                return f"{_get_source_stem(sources[0])}{ext}"

            first_line = next(
                (line.strip() for line in raw.splitlines() if line.strip()), ""
            )
            if first_line:
                if first_line.startswith("http://") or first_line.startswith(
                    "https://"
                ):
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
            self.output_dir_display_label.setText(
                f"Output directory: {output_dir_text}"
            )
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
            self.input_text.setPlainText(current + separator + "\n".join(files))

    @Slot()
    def _clear_input_files(self):
        self.input_text.setPlainText("")

    @Slot()
    def _add_pending_files_from_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select pending file(s)", "", FILE_FILTER
        )
        if files:
            self._append_pending_sources(files)

    @Slot()
    def _add_pending_directory_from_dialog(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select directory to expand into pending files"
        )
        if directory:
            self._append_pending_sources([directory])

    @Slot()
    def _add_pending_url(self):
        url = self.pending_url_edit.text().strip()
        if not url:
            return
        self.pending_url_edit.setText("")
        self._append_pending_sources([url])

    @Slot()
    def _remove_selected_pending_sources(self):
        selected_indexes = self.pending_list.selectedIndexes()
        if not selected_indexes:
            return

        selected_rows = {index.row() for index in selected_indexes}
        remaining_sources = [
            source
            for index, source in enumerate(self._workspace.pending_sources)
            if index not in selected_rows
        ]
        self._set_pending_sources(remaining_sources)

    @Slot()
    def _clear_pending_sources(self):
        self._set_pending_sources([])

    @Slot()
    def _load_workspace_from_dialog(self):
        default_dir = str(self._workspace_path.parent)
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load workspace",
            default_dir,
            "Workspace files (*.json);;All files (*)",
        )
        if selected_path:
            self._load_workspace_to_path(Path(selected_path))

    @Slot()
    def _save_workspace_from_dialog(self):
        default_path = str(self._workspace_path)
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save workspace",
            default_path,
            "Workspace files (*.json);;All files (*)",
        )
        if selected_path:
            self._save_workspace_to_path(Path(selected_path))

    @Slot()
    def _browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select output directory")
        if directory:
            self.output_dir_edit.setText(directory)

    @Slot(str)
    def _on_format_changed(self, _text: str):
        self._update_auto_filename()
        self._sync_workspace_from_ui()

    @Slot()
    def _on_sources_changed(self):
        self._update_auto_filename()
        self._sync_workspace_from_ui()

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
        self._sync_workspace_from_ui()

    @Slot(str)
    def _on_filename_edited(self, text: str):
        if self._updating_filename:
            return

        if not text.strip():
            self._auto_filename_enabled = True
            self._apply_auto_filename()
            self._sync_workspace_from_ui()
            return

        self._auto_filename_enabled = False
        self._sync_workspace_from_ui()

    @Slot()
    def _on_auto_filename_clicked(self):
        self._auto_filename_enabled = True
        self._apply_auto_filename()
        self._sync_workspace_from_ui()

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
            self._set_status_message(
                "Validation errors: " + "; ".join(errors),
                style="color: red;",
            )
            self._populate_results_table([])
            return

        # Start worker
        fmt_info = FORMAT_OPTIONS[format_label]
        self.convert_btn.setEnabled(False)
        self.clear_input_btn.setEnabled(False)
        self._set_status_message("Starting conversion...", busy=True)
        self._populate_results_table([])
        self.open_folder_btn.setVisible(False)

        assert output_dir is not None  # guaranteed by validation above
        self._worker = ConversionWorker(sources, output_dir, fmt_info, custom_filename)
        self._worker.progress.connect(self._on_progress)
        self._worker.result_ready.connect(self._on_finished)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    @Slot(str)
    def _on_progress(self, message: str):
        self._set_status_message(message, busy=True)

    @Slot(object, str)
    def _on_finished(self, payload: dict, preview: str):
        self.convert_btn.setEnabled(True)
        self.clear_input_btn.setEnabled(True)

        rows = payload.get("rows", [])
        has_errors = any(row.get("severity") == "error" for row in rows)
        if has_errors:
            self._set_status_message("Done with errors.", style="color: red;")
        else:
            self._set_status_message("Done.", style="color: green;")

        output_dir_text = payload.get("output_dir", "")
        output_dir = Path(output_dir_text) if output_dir_text else None
        if output_dir and output_dir.is_dir():
            self._last_output_dir = output_dir
            self.open_folder_btn.setVisible(True)
        else:
            self._last_output_dir = None

        self._populate_results_table(rows)
        converted_rows = [
            ConvertedItem(
                source=row.get("source", ""),
                target=row.get("target", ""),
                severity=row.get("severity", "success"),
                messages=list(row.get("messages", [])),
            )
            for row in rows
            if row.get("target")
        ]
        if converted_rows:
            self._workspace.converted_items.extend(converted_rows)
            self._refresh_converted_table()

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
