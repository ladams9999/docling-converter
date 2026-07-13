"""Pure URL, scope, and output-name helpers for wiki imports."""

from __future__ import annotations

import hashlib
import re
from enum import Enum
from urllib.parse import (
    parse_qsl,
    quote,
    unquote,
    urlencode,
    urljoin,
    urlsplit,
    urlunsplit,
)

_UNRESERVED = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)
_PATH_SAFE = "/:@!$&'()*+,;=-._~%"
_INVALID_WINDOWS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_WINDOWS_NAMES = re.compile(
    r"^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", re.IGNORECASE
)
_TRACKING_PARAMETERS = frozenset({"fbclid", "gclid"})


class SubWikiLinkKind(Enum):
    """How a URL relates to a sub-wiki starting page."""

    START_PAGE = "start-page"
    CHILD_DIRECTORY = "child-directory"
    SAME_DIRECTORY = "same-directory"
    OUTSIDE = "outside"


def _normalize_percent_encoding(value: str, *, safe: str) -> str:
    normalized: list[str] = []
    index = 0
    while index < len(value):
        if (
            value[index] == "%"
            and index + 2 < len(value)
            and all(character in "0123456789abcdefABCDEF" for character in value[index + 1 : index + 3])
        ):
            byte = int(value[index + 1 : index + 3], 16)
            character = chr(byte)
            normalized.append(character if character in _UNRESERVED else f"%{byte:02X}")
            index += 3
            continue
        normalized.append(value[index])
        index += 1
    return quote("".join(normalized), safe=safe)


def _normalize_path(path: str) -> str:
    path = _normalize_percent_encoding(path or "/", safe=_PATH_SAFE)
    trailing_slash = path.endswith("/") or path.endswith("/.") or path.endswith("/..")
    segments: list[str] = []
    for segment in path.split("/"):
        if not segment or segment == ".":
            continue
        if segment == "..":
            if segments:
                segments.pop()
            continue
        segments.append(segment)
    normalized = "/" + "/".join(segments)
    if trailing_slash and normalized != "/":
        normalized += "/"
    return normalized


def _normalized_netloc(parts) -> str:
    if parts.username is not None or parts.password is not None:
        raise ValueError("URLs containing credentials are not allowed")
    if not parts.hostname:
        raise ValueError("URL must include a hostname")
    try:
        port = parts.port
    except ValueError as error:
        raise ValueError("URL contains an invalid port") from error

    host = parts.hostname.encode("idna").decode("ascii").lower()
    if ":" in host:
        host = f"[{host}]"
    default_port = 80 if parts.scheme.lower() == "http" else 443
    return host if port is None or port == default_port else f"{host}:{port}"


def canonicalize_url(url: str, *, keep_fragment: bool = False) -> str:
    """Return the canonical HTTP(S) form of *url*.

    By default fragments are removed because the result is a page identity.
    Set ``keep_fragment`` when normalizing a navigable outgoing link.
    """

    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be a non-empty string")
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS URLs are supported")

    retained_query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not (
            key.lower() in _TRACKING_PARAMETERS
            or key.lower().startswith("utm_")
        )
    ]
    retained_query.sort()
    query = urlencode(retained_query, doseq=True)
    fragment = (
        _normalize_percent_encoding(parts.fragment, safe="!$&'()*+,;=:@/?-._~")
        if keep_fragment
        else ""
    )
    return urlunsplit(
        (
            scheme,
            _normalized_netloc(parts),
            _normalize_path(parts.path),
            query,
            fragment,
        )
    )


def resolve_url(base_url: str, link: str, *, keep_fragment: bool = False) -> str:
    """Resolve *link* against *base_url* and canonicalize the result."""

    return canonicalize_url(
        urljoin(canonicalize_url(base_url, keep_fragment=True), link),
        keep_fragment=keep_fragment,
    )


def url_origin(url: str) -> str:
    """Return the normalized scheme and authority for *url*."""

    parts = urlsplit(canonicalize_url(url))
    return f"{parts.scheme}://{parts.netloc}"


def same_origin(first_url: str, second_url: str) -> bool:
    """Return whether two URLs have the same scheme, host, and effective port."""

    return url_origin(first_url) == url_origin(second_url)


def current_directory_path(url: str) -> str:
    """Return the normalized directory path containing *url*."""

    path = urlsplit(canonicalize_url(url)).path
    if path.endswith("/"):
        return path
    return path.rsplit("/", 1)[0] + "/"


def infer_wiki_root(url: str) -> str:
    """Infer a whole-wiki root from a starting page URL."""

    canonical = urlsplit(canonicalize_url(url))
    path = canonical.path
    if not path.endswith("/"):
        path = path.rsplit("/", 1)[0] + "/"
    return urlunsplit((canonical.scheme, canonical.netloc, path, "", ""))


def _path_is_under(path: str, root_path: str) -> bool:
    if root_path == "/":
        return path.startswith("/")
    prefix = root_path if root_path.endswith("/") else root_path + "/"
    return path == root_path or path.startswith(prefix)


def is_within_root(url: str, root_url: str) -> bool:
    """Return whether *url* is on the root origin and below its path boundary."""

    canonical_url = urlsplit(canonicalize_url(url))
    canonical_root = urlsplit(canonicalize_url(root_url))
    return (
        canonical_url.scheme == canonical_root.scheme
        and canonical_url.netloc == canonical_root.netloc
        and _path_is_under(canonical_url.path, canonical_root.path)
    )


def is_same_directory(first_url: str, second_url: str) -> bool:
    """Return whether two pages are on the same origin in the same directory."""

    return same_origin(first_url, second_url) and current_directory_path(
        first_url
    ) == current_directory_path(second_url)


def is_descendant_directory(url: str, directory_url: str) -> bool:
    """Return whether *url* is in a directory strictly below *directory_url*."""

    if not same_origin(url, directory_url):
        return False
    parent = current_directory_path(directory_url)
    candidate = current_directory_path(url)
    return candidate.startswith(parent) and candidate != parent


def classify_subwiki_link(start_url: str, target_url: str) -> SubWikiLinkKind:
    """Classify a target relative to a sub-wiki's starting page."""

    start = canonicalize_url(start_url)
    target = canonicalize_url(target_url)
    if target == start:
        return SubWikiLinkKind.START_PAGE
    if not same_origin(start, target):
        return SubWikiLinkKind.OUTSIDE
    if is_descendant_directory(target, start):
        return SubWikiLinkKind.CHILD_DIRECTORY
    if is_same_directory(target, start):
        return SubWikiLinkKind.SAME_DIRECTORY
    return SubWikiLinkKind.OUTSIDE


def should_follow_subwiki_link(
    start_url: str, source_url: str, target_url: str
) -> bool:
    """Apply sub-wiki traversal rules to a link edge.

    Child-directory pages are recursive. Same-directory pages are eligible only
    when linked directly by the starting page.
    """

    kind = classify_subwiki_link(start_url, target_url)
    if kind in {SubWikiLinkKind.START_PAGE, SubWikiLinkKind.CHILD_DIRECTORY}:
        return True
    return (
        kind is SubWikiLinkKind.SAME_DIRECTORY
        and canonicalize_url(source_url) == canonicalize_url(start_url)
    )


def relative_wiki_path(url: str, root_url: str) -> str:
    """Return *url*'s encoded path relative to *root_url*.

    Query strings intentionally do not affect the preferred filename; the
    collision planner distinguishes query-specific pages with URL hashes.
    """

    if not is_within_root(url, root_url):
        raise ValueError("URL is outside the selected wiki root")
    path = urlsplit(canonicalize_url(url)).path
    root_path = urlsplit(canonicalize_url(root_url)).path
    if path == root_path:
        return ""
    prefix = root_path if root_path.endswith("/") else root_path + "/"
    return path[len(prefix) :]


def _safe_filename_stem(relative_path: str) -> str:
    trailing_slash = not relative_path or relative_path.endswith("/")
    encoded_components = [part for part in relative_path.split("/") if part]
    components = [unquote(part) for part in encoded_components]
    if components and re.search(r"\.html?$", components[-1], re.IGNORECASE):
        components[-1] = re.sub(r"\.html?$", "", components[-1], flags=re.IGNORECASE)
    if trailing_slash:
        components.append("index")

    stem = "-".join(components) or "index"
    stem = _INVALID_WINDOWS_CHARS.sub("-", stem).rstrip(" .")
    if not stem:
        stem = "index"
    if _RESERVED_WINDOWS_NAMES.match(stem):
        stem = f"_{stem}"
    return stem


def flattened_output_filename(
    url: str, root_url: str, extension: str = ".md"
) -> str:
    """Create a deterministic preferred flattened filename for a wiki page."""

    normalized_extension = extension.lower()
    if normalized_extension not in {".md", ".html"}:
        raise ValueError("Wiki output extension must be '.md' or '.html'")
    return _safe_filename_stem(relative_wiki_path(url, root_url)) + normalized_extension


def plan_output_filenames(
    urls: list[str] | tuple[str, ...] | set[str],
    root_url: str,
    extension: str = ".md",
    *,
    hash_length: int = 8,
) -> dict[str, str]:
    """Plan stable, case-insensitively unique names keyed by canonical URL."""

    if hash_length < 4:
        raise ValueError("hash_length must be at least 4")
    canonical_urls = sorted({canonicalize_url(url) for url in urls})
    result: dict[str, str] = {}
    occupied: set[str] = set()
    for url in canonical_urls:
        preferred = flattened_output_filename(url, root_url, extension)
        candidate = preferred
        if candidate.casefold() in occupied:
            stem, suffix = preferred.rsplit(".", 1)
            digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
            length = hash_length
            candidate = f"{stem}-{digest[:length]}.{suffix}"
            while candidate.casefold() in occupied:
                length += 2
                candidate = f"{stem}-{digest[:length]}.{suffix}"
        occupied.add(candidate.casefold())
        result[url] = candidate
    return result
