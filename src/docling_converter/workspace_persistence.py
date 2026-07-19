"""Disk persistence for workspace state."""

from __future__ import annotations

import json
from pathlib import Path

from docling_converter.workspace_model import WorkspaceData

WORKSPACE_FILE_VERSION = 3


def save_workspace(workspace: WorkspaceData, path: Path) -> None:
    """Persist workspace data to disk as JSON."""

    payload = {
        "version": WORKSPACE_FILE_VERSION,
        "workspace": workspace.to_dict(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_workspace(path: Path) -> WorkspaceData:
    """Load workspace data from disk."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    version = int(payload.get("version", 0))
    if version in {1, 2}:
        return WorkspaceData.from_dict(payload.get("workspace", {}))
    if version != WORKSPACE_FILE_VERSION:
        raise ValueError(f"Unsupported workspace file version: {version}")
    return WorkspaceData.from_dict(payload.get("workspace", {}))
