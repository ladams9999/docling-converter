from pathlib import Path

from docling_converter.wiki_discovery import FetchResponse, WikiCrawler
from docling_converter.wiki_urls import canonicalize_url


class FakeFetcher:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, url):
        identity = canonicalize_url(url)
        self.calls.append(identity)
        response_data = self.responses[identity]
        body, content_type = response_data[:2]
        final_url = response_data[2] if len(response_data) == 3 else identity
        return FetchResponse(
            requested_url=identity,
            final_url=final_url,
            body=body,
            content_type=content_type,
            fetched_at="2026-07-12T18:00:00Z",
        )


def test_whole_wiki_discovers_cycles_once_and_caches_provenance(tmp_path):
    root = "https://example.com/wiki/"
    start = root + "index.html#intro"
    other = root + "guide/page.html"
    fetcher = FakeFetcher(
        {
            canonicalize_url(start): (
                f'<html><a href="{other}">Guide</a></html>'.encode(),
                "text/html",
            ),
            other: (
                b'<html><a href="../index.html">Home</a></html>',
                "text/html",
            ),
        }
    )

    wiki_import, warnings = WikiCrawler(
        fetcher=fetcher, cache_root=tmp_path
    ).crawl(start, root, "whole", respect_robots_txt=False)

    assert warnings == []
    assert len(wiki_import.pages) == 2
    assert len(fetcher.calls) == 2
    assert wiki_import.pages[0].original_url.endswith("#intro")
    assert wiki_import.pages[0].fetched_at == "2026-07-12T18:00:00Z"
    snapshot = tmp_path / wiki_import.pages[0].snapshot_key
    assert snapshot.is_file()
    assert "data-docling-absolute-href" in snapshot.read_text(encoding="utf-8")
    assert (tmp_path / "manifest.json").is_file()


def test_subwiki_follows_one_same_directory_hop_and_child_pages(tmp_path):
    start = "https://example.com/docs/topic/start"
    sibling = "https://example.com/docs/topic/sibling"
    third = "https://example.com/docs/topic/third"
    child = "https://example.com/docs/topic/child/page"
    deeper = "https://example.com/docs/topic/child/deeper/page"
    responses = {
        start: (
            f'<a href="{sibling}">Sibling</a><a href="{child}">Child</a>'.encode(),
            "text/html",
        ),
        sibling: (
            f'<a href="{third}">Third</a><a href="{child}">Child</a>'.encode(),
            "text/html",
        ),
        child: (f'<a href="{deeper}">Deep</a>'.encode(), "text/html"),
        deeper: (b"<p>Done</p>", "text/html"),
    }
    fetcher = FakeFetcher(responses)

    wiki_import, _warnings = WikiCrawler(
        fetcher=fetcher, cache_root=tmp_path
    ).crawl(
        start,
        "https://example.com/docs/topic/",
        "subwiki",
        respect_robots_txt=False,
    )

    discovered = {page.canonical_url for page in wiki_import.pages}
    assert discovered == {start, sibling, child, deeper}
    assert third not in fetcher.calls


def test_optional_assets_are_cached_and_named(tmp_path):
    start = "https://example.com/wiki/page"
    image = "https://example.com/media/image.png"
    fetcher = FakeFetcher(
        {
            start: (f'<img src="{image}">'.encode(), "text/html"),
            image: (b"png-data", "image/png"),
        }
    )

    wiki_import, warnings = WikiCrawler(
        fetcher=fetcher, cache_root=tmp_path
    ).crawl(
        start,
        "https://example.com/wiki/",
        "whole",
        respect_robots_txt=False,
        download_assets=True,
    )

    assert warnings == []
    assert len(wiki_import.assets) == 1
    asset = wiki_import.assets[0]
    assert asset.output_filename == "image.png"
    assert (tmp_path / asset.snapshot_key).read_bytes() == b"png-data"


def test_redirect_aliases_deduplicate_to_one_page(tmp_path):
    root = "https://example.com/wiki/"
    start = root + "start"
    alias_one = root + "alias-one"
    alias_two = root + "alias-two"
    final = root + "final"
    fetcher = FakeFetcher(
        {
            start: (
                f'<a href="{alias_one}">One</a><a href="{alias_two}">Two</a>'.encode(),
                "text/html",
            ),
            alias_one: (b"<p>Final</p>", "text/html", final),
            alias_two: (b"<p>Final</p>", "text/html", final),
        }
    )

    wiki_import, warnings = WikiCrawler(
        fetcher=fetcher, cache_root=tmp_path
    ).crawl(start, root, "whole", respect_robots_txt=False)

    assert warnings == []
    final_pages = [page for page in wiki_import.pages if page.canonical_url == final]
    assert len(final_pages) == 1
    assert alias_one in final_pages[0].aliases
    assert alias_two in final_pages[0].aliases


def test_subwiki_rejects_child_redirect_to_same_directory(tmp_path):
    start = "https://example.com/docs/topic/start"
    child_alias = "https://example.com/docs/topic/child/page"
    escaped = "https://example.com/docs/topic/escaped"
    fetcher = FakeFetcher(
        {
            start: (f'<a href="{child_alias}">Child</a>'.encode(), "text/html"),
            child_alias: (b"<p>Moved</p>", "text/html", escaped),
        }
    )

    wiki_import, warnings = WikiCrawler(
        fetcher=fetcher, cache_root=tmp_path
    ).crawl(
        start,
        "https://example.com/docs/topic/",
        "subwiki",
        respect_robots_txt=False,
    )

    assert {page.canonical_url for page in wiki_import.pages} == {start}
    assert any("sub-wiki boundary" in warning for warning in warnings)
