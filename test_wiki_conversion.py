import hashlib
import sys
import types

from wiki_conversion import (
    WikiConversionWorker,
    add_html_provenance,
    add_markdown_provenance,
    planned_wiki_conflicts,
    rewrite_markdown_links,
)
from wiki_model import WikiAsset, WikiImport, WikiPage


def test_markdown_provenance_is_first_and_safely_quoted():
    result = add_markdown_provenance(
        "# Page", 'https://example.com/a?q="value"', "2026-07-12T18:00:00Z"
    )

    assert result.startswith("---\noriginal_url: ")
    assert 'https://example.com/a?q=\\"value\\"' in result
    assert "fetched_at: \"2026-07-12T18:00:00Z\"" in result
    assert result.endswith("# Page")


def test_html_provenance_is_first_and_keeps_comment_valid():
    result = add_html_provenance(
        "<!DOCTYPE html><html></html>",
        "https://example.com/a--b?x=<value>",
        "2026-07-12T18:00:00Z",
    )

    assert result.startswith("<!--\noriginal_url: ")
    assert "a&#45;&#45;b" in result
    assert "&lt;value&gt;" in result
    assert result.index("-->") < result.index("<!DOCTYPE html>")


def test_markdown_link_rewrite_skips_code():
    url = "https://example.com/wiki/other#part"
    markdown = f"[Other]({url})\n`[Code]({url})`\n```\n[Block]({url})\n```\n"

    result = rewrite_markdown_links(
        markdown,
        {"https://example.com/wiki/other": "other.md"},
        {},
    )

    assert "[Other](other.md#part)" in result
    assert f"`[Code]({url})`" in result
    assert f"[Block]({url})" in result


def test_markdown_link_rewrite_handles_balanced_parentheses():
    url = "https://example.com/wiki/Hyrule_(5e_Campaign_Setting)"

    result = rewrite_markdown_links(
        f"[Hyrule]({url})",
        {url: "Hyrule-5e-Campaign-Setting.md"},
        {},
    )

    assert result == "[Hyrule](Hyrule-5e-Campaign-Setting.md)"


def _cached_import(tmp_path):
    root = "https://example.com/wiki/"
    pages = []
    for index, name in enumerate(("one", "two"), 1):
        content = (
            f'<html><body><h1>Page {name.title()}</h1>'
            f'<a href="{root}two">Two</a></body></html>'
        ).encode()
        digest = hashlib.sha256(content).hexdigest()
        key = f"pages/{name}.html"
        path = tmp_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        pages.append(
            WikiPage(
                id=f"page-{index}",
                import_id="import-1",
                original_url=f"{root}{name}",
                canonical_url=f"{root}{name}",
                fetched_at=f"2026-07-12T18:00:0{index}Z",
                relative_path=name,
                output_filename=f"{name}.md",
                outgoing_urls=[f"{root}two"],
                snapshot_key=key,
                content_hash=digest,
            )
        )
    return WikiImport(
        id="import-1",
        start_url=pages[0].original_url,
        root_url=root,
        scope="whole",
        pages=pages,
    )


def test_wiki_worker_converts_cached_pages_with_links_and_provenance(
    monkeypatch, tmp_path
):
    wiki_import = _cached_import(tmp_path / "cache")
    docling_module = types.ModuleType("docling")
    converter_module = types.ModuleType("docling.document_converter")

    class FakeDocument:
        def __init__(self, html_text):
            self.html_text = html_text

        def export_to_markdown(self):
            title = "One" if "Page One" in self.html_text else "Two"
            return (
                f"# {title}\n\n"
                "[Two](https://example.com/wiki/two#details)\n"
            )

        def export_to_html(self):
            return self.html_text

    class FakeResult:
        def __init__(self, html_text):
            self.document = FakeDocument(html_text)

    class FakeConverter:
        def convert(self, path):
            return FakeResult(open(path, encoding="utf-8").read())

    converter_module.DocumentConverter = FakeConverter
    monkeypatch.setitem(sys.modules, "docling", docling_module)
    monkeypatch.setitem(sys.modules, "docling.document_converter", converter_module)
    monkeypatch.setattr(
        "wiki_conversion.get_wiki_cache_directory",
        lambda _import_id: tmp_path / "cache",
    )
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    worker = WikiConversionWorker(
        [page.original_url for page in wiki_import.pages],
        [wiki_import],
        output_dir,
        {"ext": ".md", "key": "markdown"},
        "",
    )
    captured = {}
    worker.result_ready.connect(
        lambda payload, preview: captured.update(payload=payload, preview=preview)
    )

    worker.run()

    one = (output_dir / "one.md").read_text(encoding="utf-8")
    assert one.startswith("---\noriginal_url: ")
    assert 'fetched_at: "2026-07-12T18:00:01Z"' in one
    assert "[Two](two.md#details)" in one
    assert len(captured["payload"]["rows"]) == 2
    assert not captured["payload"]["has_errors"]


def test_wiki_worker_supports_per_page_formats(monkeypatch, tmp_path):
    wiki_import = _cached_import(tmp_path / "cache")
    docling_module = types.ModuleType("docling")
    converter_module = types.ModuleType("docling.document_converter")

    class FakeDocument:
        def export_to_markdown(self):
            return "[Two](https://example.com/wiki/two)"

        def export_to_html(self):
            return '<a href="https://example.com/wiki/one">One</a>'

    class FakeResult:
        document = FakeDocument()
        errors = []
        status = "success"

    class FakeConverter:
        def convert(self, _path):
            return FakeResult()

    converter_module.DocumentConverter = FakeConverter
    monkeypatch.setitem(sys.modules, "docling", docling_module)
    monkeypatch.setitem(sys.modules, "docling.document_converter", converter_module)
    monkeypatch.setattr(
        "wiki_conversion.get_wiki_cache_directory",
        lambda _import_id: tmp_path / "cache",
    )
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    second_page = wiki_import.pages[1]
    worker = WikiConversionWorker(
        [page.original_url for page in wiki_import.pages],
        [wiki_import],
        output_dir,
        {"ext": ".md", "key": "markdown"},
        "",
        {second_page.original_url: "HTML (.html)"},
    )

    worker.run()

    assert (output_dir / "one.md").is_file()
    assert (output_dir / "two.html").is_file()
    assert "[Two](two.html)" in (output_dir / "one.md").read_text(encoding="utf-8")


def test_planned_wiki_conflicts_lists_existing_targets(tmp_path):
    wiki_import = _cached_import(tmp_path / "cache")
    existing = tmp_path / "one.md"
    existing.write_text("old", encoding="utf-8")

    conflicts = planned_wiki_conflicts(
        [page.original_url for page in wiki_import.pages],
        [wiki_import],
        tmp_path,
        ".md",
    )

    assert conflicts == [existing]


def test_planned_wiki_conflicts_include_selected_assets(tmp_path):
    wiki_import = _cached_import(tmp_path / "cache")
    asset_url = "https://example.com/media/image.png"
    wiki_import.download_assets = True
    wiki_import.pages[0].asset_urls = [asset_url]
    wiki_import.assets = [
        WikiAsset(
            original_url=asset_url,
            canonical_url=asset_url,
            fetched_at="2026-07-12T18:00:00Z",
            snapshot_key="assets/image.png",
            content_hash="abc",
            output_filename="image.png",
        )
    ]
    asset_path = tmp_path / "assets" / "image.png"
    asset_path.parent.mkdir()
    asset_path.write_bytes(b"old")

    conflicts = planned_wiki_conflicts(
        [wiki_import.pages[0].original_url],
        [wiki_import],
        tmp_path,
        ".md",
    )

    assert conflicts == [asset_path]
