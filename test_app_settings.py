from pathlib import Path

from PySide6.QtCore import QSettings

from app_settings import load_base_directory, save_base_directory


def test_base_directory_round_trip(tmp_path):
    settings = QSettings(
        str(tmp_path / "settings.ini"), QSettings.Format.IniFormat
    )
    directory = Path(r"D:\Docling Workspaces")

    save_base_directory(directory, settings)
    settings.sync()

    assert load_base_directory(settings) == directory
