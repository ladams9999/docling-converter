from pathlib import Path

from PySide6.QtCore import QSettings

from docling_converter.app_settings import (
    DEFAULT_VLM_API_URL,
    DEFAULT_VLM_MODEL,
    VlmSettings,
    load_base_directory,
    load_vlm_settings,
    save_base_directory,
    save_vlm_settings,
)


def test_base_directory_round_trip(tmp_path):
    settings = QSettings(
        str(tmp_path / "settings.ini"), QSettings.Format.IniFormat
    )
    directory = Path(r"D:\Docling Workspaces")

    save_base_directory(directory, settings)
    settings.sync()

    assert load_base_directory(settings) == directory


def test_vlm_settings_defaults_when_unset(tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)

    result = load_vlm_settings(settings)

    assert result == VlmSettings(
        enabled=False, api_url=DEFAULT_VLM_API_URL, model=DEFAULT_VLM_MODEL, api_key=""
    )


def test_vlm_settings_round_trip(tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    vlm_settings = VlmSettings(
        enabled=True,
        api_url="https://api.example.com/v1/chat/completions",
        model="some-other-vision-model",
        api_key="secret",
    )

    save_vlm_settings(vlm_settings, settings)
    settings.sync()

    assert load_vlm_settings(settings) == vlm_settings
