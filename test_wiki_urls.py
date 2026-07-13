import re

import pytest

from wiki_urls import (
    SubWikiLinkKind,
    canonicalize_url,
    classify_subwiki_link,
    flattened_output_filename,
    infer_wiki_root,
    is_descendant_directory,
    is_same_directory,
    is_within_root,
    plan_output_filenames,
    relative_wiki_path,
    resolve_url,
    same_origin,
    should_follow_subwiki_link,
)


def test_canonicalize_url_normalizes_identity_and_query():
    url = (
        "HTTPS://Example.COM:443//docs/./guide/../Page%7e.html"
        "?z=2&utm_source=x&a=3&a=1&FBCLID=id#heading"
    )

    assert canonicalize_url(url) == "https://example.com/docs/Page~.html?a=1&a=3&z=2"
    assert (
        canonicalize_url("http://EXAMPLE.com:80/%41/%2f?q=a+b&gclid=x")
        == "http://example.com/A/%2F?q=a+b"
    )


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/wiki/",
        "mailto:person@example.com",
        "https://user:secret@example.com/wiki/",
        "https:///wiki/page",
        "https://example.com:bad/wiki",
    ],
)
def test_canonicalize_url_rejects_unsafe_or_unsupported_urls(url):
    with pytest.raises(ValueError):
        canonicalize_url(url)


def test_resolve_url_supports_all_link_forms_and_optional_fragments():
    base = "https://example.com/docs/a/page.html"

    assert resolve_url(base, "../b.html") == "https://example.com/docs/b.html"
    assert resolve_url(base, "/root") == "https://example.com/root"
    assert resolve_url(base, "//EXAMPLE.com:443/x") == "https://example.com/x"
    assert resolve_url(base, "https://example.com/y?q=1") == "https://example.com/y?q=1"
    assert resolve_url(base, "?q=2#part") == "https://example.com/docs/a/page.html?q=2"
    assert resolve_url(base, "#part", keep_fragment=True).endswith("#part")


def test_root_inference_and_scope_use_origin_and_segment_boundaries():
    assert infer_wiki_root("https://example.com/docs/v1/") == "https://example.com/docs/v1/"
    assert (
        infer_wiki_root("https://example.com/docs/v1/page?q=1#x")
        == "https://example.com/docs/v1/"
    )
    root = "https://example.com/docs/"
    assert same_origin("https://EXAMPLE.com:443/a", root)
    assert is_within_root("https://example.com/docs/reference", root)
    assert not is_within_root("https://example.com/docs-other/page", root)
    assert not is_within_root("https://example.com.evil.test/docs/page", root)
    assert not is_within_root("http://example.com/docs/page", root)


def test_directory_and_subwiki_helpers_enforce_one_hop_rule():
    start = "https://example.com/docs/topic/start#section"
    sibling = "https://example.com/docs/topic/other"
    child = "https://example.com/docs/topic/child/page"

    assert classify_subwiki_link(start, start) is SubWikiLinkKind.START_PAGE
    assert classify_subwiki_link(start, sibling) is SubWikiLinkKind.SAME_DIRECTORY
    assert classify_subwiki_link(start, child) is SubWikiLinkKind.CHILD_DIRECTORY
    assert is_same_directory(start, sibling)
    assert is_descendant_directory(child, start)
    assert should_follow_subwiki_link(start, start, sibling)
    assert not should_follow_subwiki_link(start, sibling, "https://example.com/docs/topic/third")
    assert should_follow_subwiki_link(start, sibling, child)
    assert should_follow_subwiki_link(start, child, "https://example.com/docs/topic/child/deeper/page")
    assert not should_follow_subwiki_link(start, start, "https://example.com/docs/peer")


def test_relative_paths_and_flattened_names_cover_index_and_encoding():
    root = "https://example.com/wiki/"

    assert relative_wiki_path("https://example.com/wiki/a/subject/page.html", root) == (
        "a/subject/page.html"
    )
    assert (
        flattened_output_filename(
            "https://example.com/wiki/a/subject/page.html", root
        )
        == "a-subject-page.md"
    )
    assert (
        flattened_output_filename("https://example.com/wiki/a/subject/", root, ".html")
        == "a-subject-index.html"
    )
    assert flattened_output_filename("https://example.com/wiki/index.htm", root) == "index.md"
    assert flattened_output_filename(root, root) == "index.md"
    assert (
        flattened_output_filename("https://example.com/wiki/caf%C3%A9%3F.html", root)
        == "café-.md"
    )
    with pytest.raises(ValueError):
        relative_wiki_path("https://example.com/outside", root)


def test_flattened_names_are_windows_safe_and_protect_reserved_names():
    root = "https://example.com/wiki/"

    assert flattened_output_filename("https://example.com/wiki/CON.html", root) == "_CON.md"
    filename = flattened_output_filename(
        "https://example.com/wiki/a%3Ab%2Ac%3Fd%22e%3Cf%3Eg%7Ch.html", root
    )
    assert filename.endswith(".md")
    assert not re.search(r'[<>:"/\\|?*]', filename)
    assert not filename.removesuffix(".md").endswith((" ", "."))


def test_collision_planning_is_stable_case_insensitive_and_query_aware():
    root = "https://example.com/wiki/"
    urls = [
        "https://example.com/wiki/A.html",
        "https://example.com/wiki/a.html",
        "https://example.com/wiki/a.html?view=compact",
        "https://example.com/wiki/a%3Fb.html",
        "https://example.com/wiki/a%2Ab.html",
    ]

    forward = plan_output_filenames(urls, root)
    reverse = plan_output_filenames(list(reversed(urls)), root)

    assert forward == reverse
    assert len({name.casefold() for name in forward.values()}) == len(forward)
    assert any(re.search(r"-[0-9a-f]{8}\.md$", name) for name in forward.values())
