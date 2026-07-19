"""Workspace creation dialog."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


def workspace_slug(label: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", label.strip()).strip(".-_")
    return slug or "workspace"


def resolve_workspace_file(base_directory: Path, value: str) -> Path:
    candidate = Path(value.strip()).expanduser()
    if candidate.parent == Path("."):
        return base_directory / candidate
    return candidate


class NewWorkspaceDialog(QDialog):
    """Collect paths and a label for a new workspace."""

    def __init__(self, base_directory: Path, parent=None):
        super().__init__(parent)
        self.base_directory = base_directory
        self.setWindowTitle("New workspace")
        self.setMinimumWidth(580)
        self._seeded_directory = ""
        self._seeded_filename = ""

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.label_edit = QLineEdit("New workspace")
        self.directory_edit = QLineEdit()
        self.filename_edit = QLineEdit()

        directory_row = QHBoxLayout()
        directory_row.addWidget(self.directory_edit)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_directory)
        directory_row.addWidget(browse_button)

        form.addRow("Label:", self.label_edit)
        form.addRow("Directory:", directory_row)
        form.addRow("Workspace file name:", self.filename_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.label_edit.textChanged.connect(self._seed_paths)
        self._seed_paths()

    def _seed_paths(self):
        slug = workspace_slug(self.label_edit.text())
        directory = str(self.base_directory / slug)
        filename = f"{slug}.json"
        if not self.directory_edit.text().strip() or (
            self.directory_edit.text() == self._seeded_directory
        ):
            self.directory_edit.setText(directory)
        if not self.filename_edit.text().strip() or (
            self.filename_edit.text() == self._seeded_filename
        ):
            self.filename_edit.setText(filename)
        self._seeded_directory = directory
        self._seeded_filename = filename

    def _browse_directory(self):
        selected = QFileDialog.getExistingDirectory(
            self, "Select workspace output directory", self.directory_edit.text()
        )
        if selected:
            self.directory_edit.setText(selected)

    def accept(self):
        if not self.label_edit.text().strip():
            QMessageBox.warning(self, "Invalid workspace", "Enter a workspace label.")
            return
        if not self.directory_edit.text().strip():
            QMessageBox.warning(
                self, "Invalid workspace", "Enter a workspace directory."
            )
            return
        if not self.filename_edit.text().strip():
            QMessageBox.warning(
                self, "Invalid workspace", "Enter a workspace file name."
            )
            return
        super().accept()

    def values(self) -> tuple[str, Path, Path]:
        label = self.label_edit.text().strip()
        directory = Path(self.directory_edit.text().strip()).expanduser()
        workspace_file = resolve_workspace_file(
            self.base_directory, self.filename_edit.text()
        )
        return label, directory, workspace_file
