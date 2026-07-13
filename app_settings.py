"""Application-scoped settings."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from workspace_paths import get_default_base_directory

ORGANIZATION_NAME = "docling-converter"
APPLICATION_NAME = "docling-converter"
BASE_DIRECTORY_KEY = "workspace/base_directory"


def load_base_directory(settings: QSettings | None = None) -> Path:
    store = settings or QSettings(ORGANIZATION_NAME, APPLICATION_NAME)
    value = str(store.value(BASE_DIRECTORY_KEY, "")).strip()
    return Path(value) if value else get_default_base_directory()


def save_base_directory(path: Path, settings: QSettings | None = None) -> None:
    store = settings or QSettings(ORGANIZATION_NAME, APPLICATION_NAME)
    store.setValue(BASE_DIRECTORY_KEY, str(path))
