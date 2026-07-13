"""Path helpers for workspace storage."""

from __future__ import annotations

from pathlib import Path

APP_HOME_DIRNAME = ".docling-converter"
DEFAULT_WORKSPACE_DIRNAME = "default-workspace"
DEFAULT_OUTPUT_DIRNAME = "output"
DEFAULT_WORKSPACE_FILENAME = "workspace.json"
DEFAULT_WORKSPACES_DIRNAME = "workspaces"
WIKI_CACHE_DIRNAME = "cache"


def get_app_home_directory(home: Path | None = None) -> Path:
    base_home = home or Path.home()
    return base_home / APP_HOME_DIRNAME


def get_default_workspace_directory(home: Path | None = None) -> Path:
    return get_app_home_directory(home) / DEFAULT_WORKSPACE_DIRNAME


def get_default_workspace_file(home: Path | None = None) -> Path:
    return get_default_workspace_directory(home) / DEFAULT_WORKSPACE_FILENAME


def get_default_base_directory(home: Path | None = None) -> Path:
    return get_app_home_directory(home) / DEFAULT_WORKSPACES_DIRNAME


def get_default_output_directory(home: Path | None = None) -> Path:
    return get_default_workspace_directory(home) / DEFAULT_OUTPUT_DIRNAME


def get_wiki_cache_directory(
    import_id: str | None = None, home: Path | None = None
) -> Path:
    directory = get_app_home_directory(home) / WIKI_CACHE_DIRNAME / "wiki"
    return directory / import_id if import_id else directory
