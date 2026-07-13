"""PySide6 dialogs for wiki import."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from wiki_urls import canonicalize_url, infer_wiki_root


class WikiImportDialog(QDialog):
    """Collect and validate wiki discovery options."""

    def __init__(self, parent=None, initial_url: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Add wiki")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.start_url_edit = QLineEdit(initial_url)
        self.start_url_edit.setPlaceholderText("https://example.com/wiki/page")
        self.root_url_edit = QLineEdit()
        self.root_url_edit.setPlaceholderText("Inferred from starting page")
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Whole wiki", "whole")
        self.scope_combo.addItem("Sub-wiki", "subwiki")
        self.respect_robots_check = QCheckBox()
        self.respect_robots_check.setChecked(True)
        self.download_assets_check = QCheckBox()

        form.addRow("Starting page:", self.start_url_edit)
        form.addRow("Wiki root:", self.root_url_edit)
        form.addRow("Scope:", self.scope_combo)
        form.addRow("Respect robots.txt:", self.respect_robots_check)
        form.addRow("Download linked assets:", self.download_assets_check)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.start_url_edit.editingFinished.connect(self._fill_inferred_root)
        if initial_url:
            self._fill_inferred_root()

    def _fill_inferred_root(self):
        if self.root_url_edit.text().strip():
            return
        try:
            inferred = infer_wiki_root(self.start_url_edit.text().strip())
        except ValueError:
            return
        self.root_url_edit.setText(inferred)

    def accept(self):
        try:
            start_url = canonicalize_url(
                self.start_url_edit.text().strip(), keep_fragment=True
            )
            root_text = self.root_url_edit.text().strip() or infer_wiki_root(start_url)
            root_url = canonicalize_url(root_text)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid wiki URL", str(exc))
            return
        self.start_url_edit.setText(start_url)
        self.root_url_edit.setText(root_url)
        super().accept()

    def values(self) -> dict:
        return {
            "start_url": self.start_url_edit.text().strip(),
            "root_url": self.root_url_edit.text().strip(),
            "scope": self.scope_combo.currentData(),
            "respect_robots_txt": self.respect_robots_check.isChecked(),
            "download_assets": self.download_assets_check.isChecked(),
        }
