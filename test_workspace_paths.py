from pathlib import Path

from workspace_paths import (
    APP_HOME_DIRNAME,
    DEFAULT_OUTPUT_DIRNAME,
    DEFAULT_WORKSPACE_DIRNAME,
    DEFAULT_WORKSPACE_FILENAME,
    get_app_home_directory,
    get_default_output_directory,
    get_default_workspace_directory,
    get_default_workspace_file,
)


def test_get_app_home_directory_uses_provided_home():
    home = Path(r"C:\Users\tester")

    result = get_app_home_directory(home)

    assert result == home / APP_HOME_DIRNAME


def test_default_workspace_paths_share_same_root():
    home = Path(r"C:\Users\tester")

    workspace_dir = get_default_workspace_directory(home)
    workspace_file = get_default_workspace_file(home)
    output_dir = get_default_output_directory(home)

    assert workspace_dir == home / APP_HOME_DIRNAME / DEFAULT_WORKSPACE_DIRNAME
    assert workspace_file == workspace_dir / DEFAULT_WORKSPACE_FILENAME
    assert output_dir == workspace_dir / DEFAULT_OUTPUT_DIRNAME
