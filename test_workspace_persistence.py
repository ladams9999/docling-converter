from pathlib import Path

import pytest

from workspace_model import ConvertedItem, WorkspaceData, WorkspaceSettings
from workspace_persistence import (
    WORKSPACE_FILE_VERSION,
    load_workspace,
    save_workspace,
)


def test_save_workspace_round_trips_state(tmp_path):
    workspace = WorkspaceData(
        target_dir=r"C:\docs\output",
        pending_sources=[r"C:\docs\a.pdf", "https://example.com/file"],
        converted_items=[
            ConvertedItem(
                source=r"C:\docs\a.pdf",
                target="a.md",
                severity="success",
                messages=[],
            )
        ],
        settings=WorkspaceSettings(
            format_label="HTML (.html)",
            custom_filename="",
            auto_filename_enabled=True,
        ),
    )
    workspace_path = tmp_path / "saved" / "workspace.json"

    save_workspace(workspace, workspace_path)
    restored = load_workspace(workspace_path)

    assert restored == workspace


def test_save_workspace_writes_versioned_json(tmp_path):
    workspace_path = tmp_path / "workspace.json"

    save_workspace(WorkspaceData(), workspace_path)

    text = workspace_path.read_text(encoding="utf-8")
    assert f'"version": {WORKSPACE_FILE_VERSION}' in text


def test_load_workspace_rejects_unknown_version(tmp_path):
    workspace_path = tmp_path / "workspace.json"
    workspace_path.write_text(
        '{"version": 999, "workspace": {}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unsupported workspace file version: 999"):
        load_workspace(workspace_path)


def test_load_workspace_migrates_version_one(tmp_path):
    workspace_path = tmp_path / "workspace-v1.json"
    workspace_path.write_text(
        """
{
  "version": 1,
  "workspace": {
    "target_dir": "C:/docs/output",
    "pending_sources": ["https://example.com/page"],
    "converted_items": [],
    "settings": {}
  }
}
""".strip(),
        encoding="utf-8",
    )

    workspace = load_workspace(workspace_path)

    assert workspace.target_dir == "C:/docs/output"
    assert workspace.pending_sources == ["https://example.com/page"]
    assert workspace.wiki_imports == []


def test_load_workspace_migrates_version_two_with_new_defaults(tmp_path):
    workspace_path = tmp_path / "workspace-v2.json"
    workspace_path.write_text(
        '{"version": 2, "workspace": {"pending_sources": ["a.pdf"]}}',
        encoding="utf-8",
    )

    workspace = load_workspace(workspace_path)

    assert workspace.label == "Default workspace"
    assert workspace.source_formats == {}
