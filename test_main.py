import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import main


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_resolve_unique_path_returns_original_when_available(tmp_path):
    result = main._resolve_unique_path(tmp_path, "report.md")
    assert result == tmp_path / "report.md"


def test_resolve_unique_path_increments_suffix(tmp_path):
    (tmp_path / "name.ext").write_text("x", encoding="utf-8")
    (tmp_path / "name_1.ext").write_text("x", encoding="utf-8")

    result = main._resolve_unique_path(tmp_path, "name.ext")
    assert result == tmp_path / "name_2.ext"


def test_resolve_unique_path_preserves_multidot_filename(tmp_path):
    (tmp_path / "report.v1.md").write_text("x", encoding="utf-8")

    result = main._resolve_unique_path(tmp_path, "report.v1.md")
    assert result == tmp_path / "report.v1_1.md"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (Path(r"C:\\docs\\sample.pdf"), "sample"),
        ("https://example.com/path/file-name.pdf", "file-name"),
        ("https://example.com/path/", "path"),
    ],
)
def test_get_source_stem(source, expected):
    assert main._get_source_stem(source) == expected


def test_resolve_sources_ignores_blank_lines_and_accepts_urls(tmp_path):
    file_path = tmp_path / "doc.pdf"
    file_path.write_text("x", encoding="utf-8")

    raw = f"\n  {file_path}\n\nhttps://example.com/paper.pdf\n   \n"
    sources, errors = main._resolve_sources(raw)

    assert errors == []
    assert sources == [file_path, "https://example.com/paper.pdf"]


def test_resolve_sources_expands_directory_supported_only(tmp_path):
    folder = tmp_path / "inputs"
    folder.mkdir()
    supported = folder / "a.pdf"
    unsupported = folder / "z.txt"
    supported.write_text("x", encoding="utf-8")
    unsupported.write_text("x", encoding="utf-8")

    sources, errors = main._resolve_sources(str(folder))

    assert errors == []
    assert sources == [supported]


def test_resolve_sources_directory_without_supported_files_adds_error(tmp_path):
    folder = tmp_path / "empty_supported"
    folder.mkdir()
    (folder / "note.txt").write_text("x", encoding="utf-8")

    sources, errors = main._resolve_sources(str(folder))

    assert sources == []
    assert errors == [f"No supported files in directory: {folder}"]


def test_resolve_sources_missing_file_adds_error(tmp_path):
    missing = tmp_path / "missing.pdf"

    sources, errors = main._resolve_sources(str(missing))

    assert sources == []
    assert errors == [f"File not found: {missing}"]


def test_resolve_auto_output_directory_uses_first_local_parent_when_writable(tmp_path):
    input_file = tmp_path / "sample.pdf"
    input_file.write_text("x", encoding="utf-8")

    result = main._resolve_auto_output_directory([input_file])

    assert result == tmp_path


def test_resolve_auto_output_directory_falls_back_to_downloads_for_url(monkeypatch, tmp_path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    monkeypatch.setattr(main, "_get_downloads_directory", lambda: downloads)

    result = main._resolve_auto_output_directory(["https://example.com/test.pdf"])

    assert result == downloads


def test_resolve_auto_output_directory_falls_back_when_not_writable(
    monkeypatch, tmp_path
):
    input_file = tmp_path / "sample.pdf"
    input_file.write_text("x", encoding="utf-8")
    downloads = tmp_path / "Downloads"
    downloads.mkdir()

    monkeypatch.setattr(main, "_is_writable_directory", lambda _directory: False)
    monkeypatch.setattr(main, "_get_downloads_directory", lambda: downloads)

    result = main._resolve_auto_output_directory([input_file])

    assert result == downloads


class _FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class _MockConversionWorker(main.ConversionWorker):
    instances = []

    def __init__(self, sources, output_dir, fmt_info, custom_filename):
        self.sources = sources
        self.output_dir = output_dir
        self.fmt_info = fmt_info
        self.custom_filename = custom_filename
        self.progress = _FakeSignal()
        self.result_ready = _FakeSignal()
        # Suppress type checking for finished signal override
        self.finished = _FakeSignal()  # type: ignore
        self.was_started = False
        _MockConversionWorker.instances.append(self)

    def start(self, priority=None):
        self.was_started = True

    def isRunning(self):
        return False

    def wait(self, deadline=5000):  # type: ignore
        return True


def test_start_conversion_empty_input_and_output_shows_validation_errors(qapp):
    window = main.MainWindow()

    window.input_text.setPlainText("")
    window.output_dir_edit.setText("")
    window._start_conversion()

    text = window.results_text.toPlainText()
    assert "No input files specified." in text
    assert "No output directory specified." in text
    assert "Output directory does not exist" in text
    assert window._worker is None
    window.close()


def test_start_conversion_invalid_output_directory_shows_error(qapp, tmp_path):
    input_file = tmp_path / "sample.pdf"
    input_file.write_text("x", encoding="utf-8")

    window = main.MainWindow()
    window.input_text.setPlainText(str(input_file))
    window.output_dir_edit.setText(str(tmp_path / "not_there"))
    window._start_conversion()

    text = window.results_text.toPlainText()
    assert "Output directory does not exist" in text
    assert window._worker is None
    window.close()


def test_start_conversion_invalid_input_paths_show_resolve_errors(qapp, tmp_path):
    window = main.MainWindow()
    window.input_text.setPlainText(str(tmp_path / "missing.pdf"))
    window.output_dir_edit.setText(str(tmp_path))
    window._start_conversion()

    text = window.results_text.toPlainText()
    assert "File not found" in text
    assert window._worker is None
    window.close()


def test_start_conversion_valid_input_creates_worker_and_sets_ui(
    qapp, monkeypatch, tmp_path
):
    _MockConversionWorker.instances.clear()
    monkeypatch.setattr(main, "ConversionWorker", _MockConversionWorker)

    input_file = tmp_path / "sample.pdf"
    input_file.write_text("x", encoding="utf-8")

    window = main.MainWindow()
    window.input_text.setPlainText(str(input_file))
    window.output_dir_edit.setText(str(tmp_path))
    window.format_combo.setCurrentText("Markdown (.md)")
    window.filename_edit.setText(" custom.md ")
    window.results_text.setPlainText("old")
    window.preview_text.setPlainText("old")

    window._start_conversion()

    assert len(_MockConversionWorker.instances) == 1
    worker = _MockConversionWorker.instances[0]
    assert worker.sources == [input_file]
    assert worker.output_dir == tmp_path
    assert worker.fmt_info == main.FORMAT_OPTIONS["Markdown (.md)"]
    assert worker.custom_filename == "custom.md"
    assert worker.was_started is True

    assert window._worker is worker
    assert window.convert_btn.isEnabled() is False
    assert window.progress_bar.isHidden() is False
    assert window.results_text.toPlainText() == ""
    assert window.preview_text.toPlainText() == ""

    assert window._on_progress in worker.progress.callbacks
    assert window._on_finished in worker.result_ready.callbacks
    assert window._on_worker_finished in worker.finished.callbacks
    window.close()


def test_output_filename_defaults_from_first_input_and_selected_format(qapp, tmp_path):
    input_file = tmp_path / "sample.pdf"
    input_file.write_text("x", encoding="utf-8")

    window = main.MainWindow()
    assert window.filename_edit.text() == "document.md"

    window.input_text.setPlainText(str(input_file))
    assert window.filename_edit.text() == "sample.md"

    window.format_combo.setCurrentText("JSON (.json)")
    assert window.filename_edit.text() == "sample.json"
    window.close()


def test_on_sources_changed_autofills_empty_output_dir_and_sets_link(qapp, tmp_path):
    input_file = tmp_path / "sample.pdf"
    input_file.write_text("x", encoding="utf-8")

    window = main.MainWindow()
    assert window.output_dir_edit.text() == ""

    window.input_text.setPlainText(str(input_file))

    assert window.output_dir_edit.text() == str(tmp_path)
    assert "Open output directory" in window.results_text.toHtml()
    window.close()


def test_on_sources_changed_uses_downloads_for_url_only(qapp, monkeypatch, tmp_path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    monkeypatch.setattr(main, "_get_downloads_directory", lambda: downloads)

    window = main.MainWindow()
    window.input_text.setPlainText("https://example.com/paper.pdf")

    assert window.output_dir_edit.text() == str(downloads)
    assert "Open output directory" in window.results_text.toHtml()
    window.close()


def test_on_sources_changed_does_not_override_existing_output_dir(qapp, tmp_path):
    input_file = tmp_path / "sample.pdf"
    input_file.write_text("x", encoding="utf-8")
    existing_output = tmp_path / "existing"
    existing_output.mkdir()

    window = main.MainWindow()
    window.output_dir_edit.setText(str(existing_output))
    window.input_text.setPlainText(str(input_file))

    assert window.output_dir_edit.text() == str(existing_output)
    window.close()


def test_manual_filename_disables_auto_updates_until_auto_clicked(qapp, tmp_path):
    input_file = tmp_path / "sample.pdf"
    input_file.write_text("x", encoding="utf-8")

    window = main.MainWindow()
    window.input_text.setPlainText(str(input_file))
    assert window.filename_edit.text() == "sample.md"

    window.filename_edit.setText("custom-name.md")
    window._on_filename_edited("custom-name.md")

    window.format_combo.setCurrentText("HTML (.html)")
    assert window.filename_edit.text() == "custom-name.md"

    window.auto_filename_btn.click()
    assert window.filename_edit.text() == "sample.html"
    window.close()


def test_blank_manual_edit_reenables_auto_filename(qapp, tmp_path):
    input_file = tmp_path / "sample.pdf"
    input_file.write_text("x", encoding="utf-8")

    window = main.MainWindow()
    window.input_text.setPlainText(str(input_file))

    window.filename_edit.setText("custom-name.md")
    window._on_filename_edited("custom-name.md")
    window.filename_edit.setText("")
    window._on_filename_edited("")

    assert window.filename_edit.text() == "sample.md"

    window.format_combo.setCurrentText("DocTags (.doctags)")
    assert window.filename_edit.text() == "sample.doctags"
    window.close()


def test_on_finished_sets_done_state_and_plain_preview_for_json_doctags(qapp):
    window = main.MainWindow()
    window.convert_btn.setEnabled(False)
    window.progress_bar.setVisible(True)

    window.format_combo.setCurrentText("JSON (.json)")
    window._on_finished("summary", "json preview")
    assert window.status_label.text() == "Done."
    assert window.convert_btn.isEnabled() is True
    assert window.progress_bar.isVisible() is False
    assert window.results_text.toPlainText() == "summary"
    assert window.preview_text.toPlainText() == "json preview"

    window.convert_btn.setEnabled(False)
    window.progress_bar.setVisible(True)
    window.format_combo.setCurrentText("DocTags (.doctags)")
    window._on_finished("summary2", "tags preview")
    assert window.status_label.text() == "Done."
    assert window.convert_btn.isEnabled() is True
    assert window.progress_bar.isVisible() is False
    assert window.preview_text.toPlainText() == "tags preview"
    window.close()


def test_on_finished_uses_markdown_and_html_branches(qapp):
    window = main.MainWindow()

    window.format_combo.setCurrentText("Markdown (.md)")
    window._on_finished("md summary", "# title")
    assert window.results_text.toPlainText() == "md summary"

    window.format_combo.setCurrentText("HTML (.html)")
    window._on_finished("html summary", "<h1>Title</h1>")
    assert window.results_text.toPlainText() == "html summary"
    assert "Title" in window.preview_text.toPlainText()
    window.close()


def test_on_finished_includes_output_directory_link_when_directory_exists(qapp, tmp_path):
    window = main.MainWindow()
    window.output_dir_edit.setText(str(tmp_path))

    window._on_finished("summary", "preview")

    assert "summary" in window.results_text.toPlainText()
    assert "Open output directory" in window.results_text.toHtml()
    window.close()


def test_on_worker_finished_clears_worker_reference(qapp):
    window = main.MainWindow()
    window._worker = _MockConversionWorker([], Path.cwd(), {}, "")

    window._on_worker_finished()

    assert window._worker is None
    window.close()


def test_close_event_waits_for_running_worker(qapp):
    class _RunningWorker(main.ConversionWorker):
        def __init__(self):
            self.wait_called_with = None

        def isRunning(self):
            return True

        def wait(self, deadline=5000) -> bool:
            self.wait_called_with = deadline
            return True

    window = main.MainWindow()
    running_worker = _RunningWorker()
    window._worker = running_worker

    window.close()

    assert running_worker.wait_called_with == 5000
