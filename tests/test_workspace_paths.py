from pathlib import Path

from docling_converter.workspace_paths import (
    APP_HOME_DIRNAME,
    DEFAULT_OUTPUT_DIRNAME,
    DEFAULT_WORKSPACES_DIRNAME,
    DEFAULT_WORKSPACE_DIRNAME,
    DEFAULT_WORKSPACE_FILENAME,
    WIKI_CACHE_DIRNAME,
    get_app_home_directory,
    get_default_output_directory,
    get_default_base_directory,
    get_default_workspace_directory,
    get_default_workspace_file,
    get_wiki_cache_directory,
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


def test_wiki_cache_directory_can_target_import():
    home = Path(r"C:\Users\tester")

    result = get_wiki_cache_directory("import-1", home)

    assert result == home / APP_HOME_DIRNAME / WIKI_CACHE_DIRNAME / "wiki" / "import-1"


def test_default_base_directory_is_under_application_home():
    home = Path(r"C:\Users\tester")

    assert get_default_base_directory(home) == (
        home / APP_HOME_DIRNAME / DEFAULT_WORKSPACES_DIRNAME
    )
