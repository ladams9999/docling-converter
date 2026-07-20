import os
import sys
import types
import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from docling_converter import main
from docling_converter.workspace_model import ConvertedItem, WorkspaceData, WorkspaceSettings
from docling_converter.workspace_persistence import save_workspace
from docling_converter.wiki_model import WikiImport, WikiPage


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
    unsupported = folder / "z.rtf"
    supported.write_text("x", encoding="utf-8")
    unsupported.write_text("x", encoding="utf-8")

    sources, errors = main._resolve_sources(str(folder))

    assert errors == []
    assert sources == [supported]


def test_resolve_sources_expands_directory_includes_epub_and_txt(tmp_path):
    folder = tmp_path / "inputs"
    folder.mkdir()
    epub = folder / "book.epub"
    txt = folder / "notes.txt"
    epub.write_text("x", encoding="utf-8")
    txt.write_text("x", encoding="utf-8")

    sources, errors = main._resolve_sources(str(folder))

    assert errors == []
    assert sources == [epub, txt]


def test_resolve_sources_directory_without_supported_files_adds_error(tmp_path):
    folder = tmp_path / "empty_supported"
    folder.mkdir()
    (folder / "note.rtf").write_text("x", encoding="utf-8")

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


def test_resolve_auto_output_directory_falls_back_to_downloads_for_url(
    monkeypatch, tmp_path
):
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


def test_should_chunk_pdf_by_page_count():
    should_chunk, reason = main._should_chunk_pdf(31, 1.0)
    assert should_chunk is True
    assert "page count" in reason


def test_should_chunk_pdf_by_size_mb():
    should_chunk, reason = main._should_chunk_pdf(10, 5.1)
    assert should_chunk is True
    assert "size" in reason


def test_should_not_chunk_small_pdf():
    should_chunk, reason = main._should_chunk_pdf(10, 4.0)
    assert should_chunk is False
    assert reason == ""


def test_combine_chunk_contents_html_wraps_sections():
    html_one = "<html><body><h1>A</h1></body></html>"
    html_two = "<html><body><p>B</p></body></html>"

    merged = main._combine_chunk_contents("html", [html_one, html_two])

    assert merged.startswith("<!DOCTYPE html><html><body>")
    assert "<section><h1>A</h1></section>" in merged
    assert "<section><p>B</p></section>" in merged


def test_combine_chunk_contents_json_merges_nested_lists():
    chunk_one = json.dumps({"pages": [1], "meta": {"title": "Doc"}})
    chunk_two = json.dumps({"pages": [2], "meta": {"author": "A"}})

    merged = json.loads(main._combine_chunk_contents("json", [chunk_one, chunk_two]))

    assert merged["pages"] == [1, 2]
    assert merged["meta"]["title"] == "Doc"
    assert merged["meta"]["author"] == "A"


def test_worker_chunks_large_pdf_and_recombines_markdown(monkeypatch, tmp_path):
    source_pdf = tmp_path / "big.pdf"
    source_pdf.write_bytes(b"%PDF-1.4")

    chunk_dir = tmp_path / "chunks"
    chunk_dir.mkdir()
    chunk_one = chunk_dir / "chunk_1.pdf"
    chunk_two = chunk_dir / "chunk_2.pdf"
    chunk_one.write_bytes(b"%PDF-1.4")
    chunk_two.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(main, "_get_pdf_page_count", lambda _path: 45)
    monkeypatch.setattr(main, "_get_file_size_mb", lambda _path: 1.0)
    monkeypatch.setattr(
        main,
        "_split_pdf_into_chunks",
        lambda _path, _size: ([chunk_one, chunk_two], chunk_dir),
    )

    docling_module = types.ModuleType("docling")
    converter_module = types.ModuleType("docling.document_converter")

    class _FakeDocument:
        def __init__(self, source: str):
            self.source = source

        def export_to_markdown(self):
            return f"md-{Path(self.source).stem}"

        def export_to_html(self):
            return "<html><body>x</body></html>"

        def model_dump_json(self, indent=2):
            return json.dumps({"source": self.source}, indent=indent)

        def export_to_doctags(self):
            return f"tags-{self.source}"

    class _FakeResult:
        def __init__(self, source: str):
            self.document = _FakeDocument(source)
            self.status = "success"
            self.errors = []

    class _FakeConverter:
        calls = []

        def convert(self, source: str):
            self.__class__.calls.append(source)
            return _FakeResult(source)

    converter_module.DocumentConverter = _FakeConverter
    monkeypatch.setitem(sys.modules, "docling", docling_module)
    monkeypatch.setitem(sys.modules, "docling.document_converter", converter_module)

    worker = main.ConversionWorker(
        [source_pdf],
        tmp_path,
        main.FORMAT_OPTIONS["Markdown (.md)"],
        "",
    )

    captured = {}
    worker.result_ready.connect(
        lambda payload, preview: captured.update({"payload": payload, "preview": preview})
    )
    worker.run()

    output_file = tmp_path / "big.md"
    assert output_file.exists()
    assert output_file.read_text(encoding="utf-8") == "md-chunk_1\n\nmd-chunk_2"
    assert len(_FakeConverter.calls) == 2
    assert captured["preview"] == "md-chunk_1\n\nmd-chunk_2"
    assert captured["payload"]["rows"][0]["severity"] in {"success", "warning"}


def _install_fake_docling_format_options(monkeypatch):
    """Install fake docling modules that record DocumentConverter's format_options."""

    class _FakeInputFormat:
        PDF = "pdf"
        IMAGE = "image"

    class _FakePipelineOptions:
        def __init__(self):
            self.do_picture_description = False
            self.enable_remote_services = False
            self.picture_description_options = None

    class _FakePictureDescriptionApiOptions:
        def __init__(self, url, params, headers, timeout):
            self.url = url
            self.params = params
            self.headers = headers
            self.timeout = timeout

    class _FakeFormatOption:
        def __init__(self, pipeline_options):
            self.pipeline_options = pipeline_options

    converter_calls = []

    class _FakeConverter:
        def __init__(self, format_options=None):
            self.format_options = format_options
            converter_calls.append(self)

    base_models_module = types.ModuleType("docling.datamodel.base_models")
    base_models_module.InputFormat = _FakeInputFormat

    pipeline_options_module = types.ModuleType("docling.datamodel.pipeline_options")
    pipeline_options_module.PdfPipelineOptions = _FakePipelineOptions
    pipeline_options_module.PictureDescriptionApiOptions = (
        _FakePictureDescriptionApiOptions
    )

    converter_module = types.ModuleType("docling.document_converter")
    converter_module.DocumentConverter = _FakeConverter
    converter_module.PdfFormatOption = _FakeFormatOption
    converter_module.ImageFormatOption = _FakeFormatOption

    docling_module = types.ModuleType("docling")
    docling_module.__path__ = []
    datamodel_module = types.ModuleType("docling.datamodel")
    datamodel_module.__path__ = []

    monkeypatch.setitem(sys.modules, "docling", docling_module)
    monkeypatch.setitem(sys.modules, "docling.datamodel", datamodel_module)
    monkeypatch.setitem(sys.modules, "docling.datamodel.base_models", base_models_module)
    monkeypatch.setitem(
        sys.modules, "docling.datamodel.pipeline_options", pipeline_options_module
    )
    monkeypatch.setitem(sys.modules, "docling.document_converter", converter_module)

    return converter_calls


def test_build_document_converter_disabled_returns_plain_converter(monkeypatch):
    from docling_converter import conversion_logic
    from docling_converter.workspace_model import VlmSettings

    converter_calls = _install_fake_docling_format_options(monkeypatch)

    conversion_logic._build_document_converter(VlmSettings(enabled=False))

    assert len(converter_calls) == 1
    assert converter_calls[0].format_options is None


def test_build_document_converter_enabled_wires_picture_description(monkeypatch):
    from docling_converter import conversion_logic
    from docling_converter.workspace_model import VlmSettings

    converter_calls = _install_fake_docling_format_options(monkeypatch)

    vlm_settings = VlmSettings(
        enabled=True,
        api_url="http://localhost:11434/v1/chat/completions",
        model="granite3.2-vision:2b",
        api_key="secret",
    )
    conversion_logic._build_document_converter(vlm_settings)

    assert len(converter_calls) == 1
    format_options = converter_calls[0].format_options
    assert set(format_options.keys()) == {"pdf", "image"}
    for option in format_options.values():
        pipeline_options = option.pipeline_options
        assert pipeline_options.do_picture_description is True
        assert pipeline_options.enable_remote_services is True
        desc_options = pipeline_options.picture_description_options
        assert desc_options.url == "http://localhost:11434/v1/chat/completions"
        assert desc_options.params == {"model": "granite3.2-vision:2b"}
        assert desc_options.headers == {"Authorization": "Bearer secret"}


class _FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class _MockConversionWorker(main.ConversionWorker):
    instances = []

    def __init__(
        self,
        sources,
        output_dir,
        fmt_info,
        custom_filename,
        source_formats=None,
        vlm_settings=None,
    ):
        self.sources = sources
        self.output_dir = output_dir
        self.fmt_info = fmt_info
        self.custom_filename = custom_filename
        self.source_formats = source_formats or {}
        self.vlm_settings = vlm_settings
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

    assert window._worker is None
    window.close()


def test_start_conversion_invalid_output_directory_shows_error(qapp, tmp_path):
    input_file = tmp_path / "sample.pdf"
    input_file.write_text("x", encoding="utf-8")

    window = main.MainWindow()
    window.input_text.setPlainText(str(input_file))
    window.output_dir_edit.setText(str(tmp_path / "not_there"))
    window._start_conversion()

    assert window._worker is None
    window.close()


def test_start_conversion_invalid_input_paths_show_resolve_errors(qapp, tmp_path):
    window = main.MainWindow()
    window.input_text.setPlainText(str(tmp_path / "missing.pdf"))
    window.output_dir_edit.setText(str(tmp_path))
    window._start_conversion()

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

    window._start_conversion()

    assert len(_MockConversionWorker.instances) == 1
    worker = _MockConversionWorker.instances[0]
    assert worker.sources == [input_file]
    assert worker.output_dir == tmp_path
    assert worker.fmt_info == main.FORMAT_OPTIONS["Markdown (.md)"]
    assert worker.custom_filename == "custom.md"
    assert worker.was_started is True

    assert window._worker is worker
    assert window.pending_convert_btn.isEnabled() is False
    assert window.pending_progress_bar.isHidden() is False

    assert window._on_progress in worker.progress.callbacks
    assert window._on_finished in worker.result_ready.callbacks
    assert window._on_worker_finished in worker.finished.callbacks
    window.close()


def test_pending_convert_button_starts_worker_from_workspace_queue(
    qapp, monkeypatch, tmp_path
):
    _MockConversionWorker.instances.clear()
    monkeypatch.setattr(main, "ConversionWorker", _MockConversionWorker)

    input_file = tmp_path / "queued.pdf"
    input_file.write_text("x", encoding="utf-8")

    window = main.MainWindow()
    window._append_pending_sources([str(input_file)])
    window.output_dir_edit.setText(str(tmp_path))

    window.pending_convert_btn.click()

    assert len(_MockConversionWorker.instances) == 1
    worker = _MockConversionWorker.instances[0]
    assert worker.sources == [input_file]
    assert window.pending_convert_btn.isEnabled() is False
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


def test_main_window_builds_required_tabs(qapp):
    window = main.MainWindow()

    labels = [window.tabs.tabText(index) for index in range(window.tabs.count())]

    assert labels == ["Settings", "Workspace", "Pending", "Converted"]
    window.close()


def test_create_new_workspace_seeds_label_directory_and_file(qapp, tmp_path):
    output_directory = tmp_path / "research"
    workspace_path = tmp_path / "research.json"
    window = main.MainWindow()

    window._create_new_workspace("Research", output_directory, workspace_path)

    restored = main.load_workspace(workspace_path)
    assert restored.label == "Research"
    assert restored.target_dir == str(output_directory)
    assert output_directory.is_dir()
    assert window.workspace_label_edit.text() == "Research"
    assert "Research" in window.workspace_path_label.text()
    window.close()


def test_workspace_input_format_changes_derived_output_file(qapp, tmp_path):
    input_file = tmp_path / "sample.pdf"
    input_file.write_text("x", encoding="utf-8")
    window = main.MainWindow()

    window._append_pending_sources([str(input_file)])

    assert window.input_files_table.rowCount() == 1
    assert window.output_files_list.item(0).text() == "sample.md"
    format_combo = window.input_files_table.cellWidget(0, 1)
    format_combo.setCurrentText("HTML (.html)")
    assert window._workspace.source_formats[str(input_file.resolve())] == (
        "HTML (.html)"
    )
    assert window.output_files_list.item(0).text() == "sample.html"
    window.close()


def test_output_files_list_plans_unique_ordinary_names(qapp, tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "report.pdf"
    second = second_dir / "report.pdf"
    first.write_text("x", encoding="utf-8")
    second.write_text("x", encoding="utf-8")
    (tmp_path / "report.md").write_text("existing", encoding="utf-8")
    window = main.MainWindow()

    window.output_dir_edit.setText(str(tmp_path))
    window._append_pending_sources([str(first), str(second)])

    assert [
        window.output_files_list.item(index).text()
        for index in range(window.output_files_list.count())
    ] == ["report_1.md", "report_2.md"]
    window.close()


def test_save_workspace_to_path_persists_current_ui_state(qapp, tmp_path):
    input_file = tmp_path / "sample.pdf"
    input_file.write_text("x", encoding="utf-8")
    workspace_path = tmp_path / "saved" / "workspace.json"

    window = main.MainWindow()
    window.input_text.setPlainText(str(input_file))
    window.output_dir_edit.setText(str(tmp_path))
    window.format_combo.setCurrentText("JSON (.json)")
    window.filename_edit.setText("bundle.json")
    window._on_filename_edited("bundle.json")

    window._save_workspace_to_path(workspace_path)

    restored = main.load_workspace(workspace_path)
    assert restored.target_dir == str(tmp_path)
    assert restored.pending_sources == [str(input_file.resolve())]
    assert restored.settings.format_label == "JSON (.json)"
    assert restored.settings.custom_filename == "bundle.json"
    assert restored.settings.auto_filename_enabled is False
    window.close()


def test_load_workspace_to_path_applies_workspace_state(qapp, tmp_path):
    workspace = WorkspaceData(
        target_dir=str(tmp_path),
        pending_sources=[str(tmp_path / "sample.pdf"), "https://example.com/doc"],
        converted_items=[
            ConvertedItem(
                source=str(tmp_path / "sample.pdf"),
                target="sample.md",
                severity="success",
                messages=[],
            )
        ],
        settings=WorkspaceSettings(
            format_label="HTML (.html)",
            custom_filename="custom.html",
            auto_filename_enabled=False,
        ),
    )
    workspace_path = tmp_path / "workspace.json"
    save_workspace(workspace, workspace_path)

    window = main.MainWindow()
    window._load_workspace_to_path(workspace_path)

    assert window.output_dir_edit.text() == str(tmp_path)
    assert (
        window.input_text.toPlainText()
        == f"{tmp_path / 'sample.pdf'}\nhttps://example.com/doc"
    )
    assert window.format_combo.currentText() == "HTML (.html)"
    assert window.filename_edit.text() == "custom.html"
    assert window.workspace_path_label.text() == (
        f"Default workspace - Workspace file: {workspace_path}"
    )
    assert window.converted_table.rowCount() == 1
    assert window.converted_table.item(0, 2).text() == "sample.md"
    window.close()


def test_append_pending_sources_expands_directory_and_updates_queue(qapp, tmp_path):
    folder = tmp_path / "inputs"
    folder.mkdir()
    supported = folder / "a.pdf"
    supported.write_text("x", encoding="utf-8")
    (folder / "note.rtf").write_text("x", encoding="utf-8")

    window = main.MainWindow()
    window._append_pending_sources([str(folder), "https://example.com/doc"])

    assert window._workspace.pending_sources == [
        str(supported.resolve()),
        "https://example.com/doc",
    ]
    assert window.input_files_table.rowCount() == 2
    assert window.input_text.toPlainText() == (
        f"{supported.resolve()}\nhttps://example.com/doc"
    )
    window.close()


def test_remove_selected_pending_sources_updates_workspace_and_input(qapp, tmp_path):
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    first.write_text("x", encoding="utf-8")
    second.write_text("x", encoding="utf-8")

    window = main.MainWindow()
    window._append_pending_sources([str(first), str(second)])
    window.input_files_table.selectRow(0)

    window._remove_selected_pending_sources()

    assert window._workspace.pending_sources == [str(second.resolve())]
    assert window.input_text.toPlainText() == str(second.resolve())
    window.close()


def test_discovered_wiki_pages_join_pending_and_removal_excludes_page(qapp):
    window = main.MainWindow()
    page = WikiPage(
        id="page-1",
        import_id="import-1",
        original_url="https://example.com/wiki/page",
        canonical_url="https://example.com/wiki/page",
        fetched_at="2026-07-12T18:00:00Z",
        relative_path="page",
        output_filename="page.md",
        snapshot_key="pages/page.html",
        content_hash="abc",
    )
    wiki_import = WikiImport(
        id="import-1",
        start_url=page.original_url,
        root_url="https://example.com/wiki/",
        scope="whole",
        pages=[page],
    )

    window._on_wiki_discovered(wiki_import, [])

    assert window._workspace.wiki_imports == [wiki_import]
    assert window._workspace.pending_sources == [page.original_url]
    assert window.input_files_table.rowCount() == 1

    window.input_files_table.selectRow(0)
    window._remove_selected_pending_sources()

    assert page.included is False
    assert window._workspace.pending_sources == []
    window.close()


def test_wiki_batch_rejects_json_before_starting_worker(qapp, tmp_path):
    window = main.MainWindow()
    page = WikiPage(
        id="page-1",
        import_id="import-1",
        original_url="https://example.com/wiki/page",
        canonical_url="https://example.com/wiki/page",
        fetched_at="2026-07-12T18:00:00Z",
        relative_path="page",
        output_filename="page.md",
    )
    window._workspace.wiki_imports = [
        WikiImport(
            id="import-1",
            start_url=page.original_url,
            root_url="https://example.com/wiki/",
            scope="whole",
            pages=[page],
        )
    ]
    window._set_pending_sources([page.original_url])
    window.output_dir_edit.setText(str(tmp_path))
    window._set_source_format(page.original_url, "JSON (.json)")

    window._start_conversion()

    assert window._worker is None
    assert "Markdown and HTML only" in window.pending_status_label.text()
    window.close()


def test_wiki_batch_rejects_mixed_ordinary_sources(qapp, tmp_path):
    local_file = tmp_path / "local.html"
    local_file.write_text("<p>Local</p>", encoding="utf-8")
    page = WikiPage(
        id="page-1",
        import_id="import-1",
        original_url="https://example.com/wiki/page",
        canonical_url="https://example.com/wiki/page",
        fetched_at="2026-07-12T18:00:00Z",
        relative_path="page",
        output_filename="page.md",
    )
    window = main.MainWindow()
    window._workspace.wiki_imports = [
        WikiImport(
            id="import-1",
            start_url=page.original_url,
            root_url="https://example.com/wiki/",
            scope="whole",
            pages=[page],
        )
    ]
    window._set_pending_sources([page.original_url, str(local_file)])
    window.output_dir_edit.setText(str(tmp_path))

    window._start_conversion()

    assert window._worker is None
    assert "separately" in window.pending_status_label.text()
    window.close()


def test_set_status_message_updates_shared_progress_views(qapp):
    window = main.MainWindow()

    window._set_status_message("Working...", busy=True, style="color: blue;")

    assert window.pending_status_label.text() == "Working..."
    assert window.converted_status_label.text() == "Working..."
    assert window.pending_progress_bar.isHidden() is False
    assert window.converted_progress_bar.isHidden() is False
    window.close()


def test_on_finished_updates_converted_history(qapp):
    window = main.MainWindow()
    window._workspace.pending_sources = ["C:/docs/a.pdf"]

    payload = {
        "rows": [
            {
                "severity": "success",
                "source": "C:/docs/a.pdf",
                "target": "a.md",
                "messages": [],
            }
        ],
        "summary": "done",
        "has_errors": False,
        "output_dir": "",
    }

    window._on_finished(payload, "# preview")

    assert len(window._workspace.converted_items) == 1
    assert window._workspace.converted_items[0].target == "a.md"
    assert window._workspace.pending_sources == []
    assert window.converted_table.rowCount() == 1
    assert window.converted_table.item(0, 1).text() == "C:/docs/a.pdf"
    assert window._last_run_sources == {"C:/docs/a.pdf"}
    assert window.converted_table.item(0, 1).font().bold() is True
    window.close()


def test_on_sources_changed_autofills_empty_output_dir_and_sets_link(qapp, tmp_path):
    input_file = tmp_path / "sample.pdf"
    input_file.write_text("x", encoding="utf-8")

    window = main.MainWindow()
    assert window.output_dir_edit.text() == ""

    window.input_text.setPlainText(str(input_file))

    assert window.output_dir_edit.text() == str(tmp_path)
    assert window.output_dir_display_label.text() == f"Output directory: {tmp_path}"
    window.close()


def test_on_sources_changed_uses_downloads_for_url_only(qapp, monkeypatch, tmp_path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    monkeypatch.setattr(main, "_get_downloads_directory", lambda: downloads)

    window = main.MainWindow()
    window.input_text.setPlainText("https://example.com/paper.pdf")

    assert window.output_dir_edit.text() == str(downloads)
    assert window.output_dir_display_label.text() == f"Output directory: {downloads}"
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


def test_on_finished_sets_done_state_and_table_for_json_doctags(qapp):
    window = main.MainWindow()
    window.pending_convert_btn.setEnabled(False)
    window.pending_progress_bar.setVisible(True)

    payload = {
        "rows": [
            {
                "severity": "success",
                "source": "C:/docs/a.pdf",
                "target": "a.json",
                "messages": [],
            }
        ],
        "summary": "✅  C:/docs/a.pdf  ->  a.json",
        "has_errors": False,
        "output_dir": "",
    }

    window.format_combo.setCurrentText("JSON (.json)")
    window._on_finished(payload, "json preview")
    assert window.pending_status_label.text() == "Done."
    assert window.pending_convert_btn.isEnabled() is True
    assert window.pending_progress_bar.isVisible() is False
    assert window.converted_table.rowCount() == 1
    assert "OK" in window.converted_table.item(0, 0).text()
    assert window.converted_table.item(0, 1).text() == "C:/docs/a.pdf"
    assert window.converted_table.item(0, 2).text() == "a.json"

    window.pending_convert_btn.setEnabled(False)
    window.pending_progress_bar.setVisible(True)
    window.format_combo.setCurrentText("DocTags (.doctags)")
    window._on_finished(payload, "tags preview")
    assert window.pending_status_label.text() == "Done."
    assert window.pending_convert_btn.isEnabled() is True
    assert window.pending_progress_bar.isVisible() is False
    assert window.converted_table.rowCount() == 2
    window.close()


def test_on_finished_uses_markdown_and_html_branches(qapp):
    window = main.MainWindow()
    payload = {
        "rows": [
            {
                "severity": "success",
                "source": "C:/docs/a.pdf",
                "target": "a.md",
                "messages": [],
            }
        ],
        "summary": "✅  C:/docs/a.pdf  ->  a.md",
        "has_errors": False,
        "output_dir": "",
    }

    window.format_combo.setCurrentText("Markdown (.md)")
    window._on_finished(payload, "# title")
    assert window.converted_table.rowCount() == 1

    window.format_combo.setCurrentText("HTML (.html)")
    window._on_finished(payload, "<h1>Title</h1>")
    assert window.converted_table.rowCount() == 2
    window.close()


def test_on_finished_includes_output_directory_link_when_directory_exists(
    qapp, tmp_path
):
    window = main.MainWindow()
    window.output_dir_edit.setText(str(tmp_path))

    payload = {
        "rows": [
            {
                "severity": "success",
                "source": str(tmp_path / "sample.pdf"),
                "target": "sample.md",
                "messages": [],
            }
        ],
        "summary": "✅  sample",
        "has_errors": False,
        "output_dir": str(tmp_path),
    }

    window._on_finished(payload, "preview")

    assert window.open_folder_btn.isHidden() is False
    assert window.open_folder_btn.text() == "Open output directory"
    assert window.output_dir_display_label.text() == f"Output directory: {tmp_path}"
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
