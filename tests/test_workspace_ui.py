from pathlib import Path

from docling_converter.workspace_ui import resolve_workspace_file, workspace_slug


def test_workspace_slug_is_filename_safe():
    assert workspace_slug(" My Research / Notes ") == "My-Research-Notes"


def test_workspace_filename_without_parent_uses_base_directory():
    base = Path(r"C:\workspaces")

    assert resolve_workspace_file(base, "research.json") == base / "research.json"


def test_workspace_filename_with_path_is_used_as_entered():
    path = Path(r"D:\projects\research.json")

    assert resolve_workspace_file(Path(r"C:\workspaces"), str(path)) == path
