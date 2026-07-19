"""Cached discovery of generic wiki-like HTML sites."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import mimetypes
import re
import socket
import threading
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from PySide6.QtCore import QThread, Signal

from docling_converter.wiki_model import WikiAsset, WikiImport, WikiPage
from docling_converter.wiki_urls import (
    canonicalize_url,
    flattened_output_filename,
    is_within_root,
    plan_output_filenames,
    relative_wiki_path,
    resolve_url,
    should_follow_subwiki_link,
)
from docling_converter.workspace_paths import get_wiki_cache_directory

USER_AGENT = "docling-converter/0.1 wiki-import"
MAX_RESPONSE_BYTES = 20 * 1024 * 1024
MAX_ASSET_TOTAL_BYTES = 250 * 1024 * 1024
_NON_HTML_EXTENSIONS = {
    ".7z",
    ".avi",
    ".bmp",
    ".css",
    ".csv",
    ".doc",
    ".docx",
    ".epub",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".m4a",
    ".mov",
    ".mp3",
    ".mp4",
    ".odt",
    ".ogg",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".svg",
    ".tar",
    ".tif",
    ".tiff",
    ".txt",
    ".wav",
    ".webm",
    ".webp",
    ".xls",
    ".xlsx",
    ".xml",
    ".zip",
}
_ACTION_QUERY_KEYS = {
    "action",
    "diff",
    "edit",
    "history",
    "login",
    "logout",
    "oldid",
    "printable",
    "raw",
    "search",
    "upload",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(slots=True)
class FetchResponse:
    """Downloaded response data used by the crawler and test fetchers."""

    requested_url: str
    final_url: str
    body: bytes
    content_type: str
    fetched_at: str


def _ensure_public_http_url(url: str) -> None:
    canonical = canonicalize_url(url)
    host = urlsplit(canonical).hostname
    if not host:
        raise ValueError("URL has no hostname")
    try:
        addresses = {
            item[4][0] for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        }
    except socket.gaierror as exc:
        raise ValueError(f"Unable to resolve host: {host}") from exc
    if not addresses:
        raise ValueError(f"Unable to resolve host: {host}")
    for address in addresses:
        parsed = ipaddress.ip_address(address)
        if not parsed.is_global:
            raise ValueError(f"Private or local network address is not allowed: {host}")


def fetch_url(url: str) -> FetchResponse:
    """Fetch one public HTTP(S) URL with bounded response size."""

    requested = canonicalize_url(url)
    _ensure_public_http_url(requested)
    class NoRedirectHandler(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = build_opener(NoRedirectHandler())
    current_url = requested
    response = None
    for _redirect_count in range(11):
        _ensure_public_http_url(current_url)
        request = Request(current_url, headers={"User-Agent": USER_AGENT})
        try:
            response = opener.open(request, timeout=30)
            break
        except HTTPError as exc:
            if exc.code not in {301, 302, 303, 307, 308}:
                raise
            location = exc.headers.get("Location")
            if not location:
                raise ValueError("Redirect response has no Location header") from exc
            current_url = canonicalize_url(urljoin(current_url, location))
    else:
        raise ValueError("Too many redirects")

    assert response is not None
    with response:
        final_url = canonicalize_url(current_url)
        content_type = response.headers.get_content_type()
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError(f"Response exceeds {MAX_RESPONSE_BYTES} bytes")
    return FetchResponse(
        requested_url=requested,
        final_url=final_url,
        body=body,
        content_type=content_type,
        fetched_at=_utc_now(),
    )


class RobotsPolicy:
    """Per-origin robots.txt cache."""

    def __init__(self):
        self._parsers: dict[str, RobotFileParser] = {}

    def can_fetch(self, url: str) -> bool:
        parts = urlsplit(canonicalize_url(url))
        origin = f"{parts.scheme}://{parts.netloc}"
        parser = self._parsers.get(origin)
        if parser is None:
            robots_url = f"{origin}/robots.txt"
            parser = RobotFileParser()
            parser.set_url(robots_url)
            try:
                response = fetch_url(robots_url)
                parser.parse(response.body.decode("utf-8", errors="replace").splitlines())
            except (OSError, ValueError):
                parser.parse([])
            self._parsers[origin] = parser
        return parser.can_fetch(USER_AGENT, url)


def _looks_like_page(url: str) -> bool:
    parts = urlsplit(url)
    extension = Path(parts.path).suffix.lower()
    if extension in _NON_HTML_EXTENSIONS:
        return False
    query_keys = {item.split("=", 1)[0].lower() for item in parts.query.split("&") if item}
    return not bool(query_keys & _ACTION_QUERY_KEYS)


def _safe_asset_filename(
    url: str, occupied: set[str], fallback_suffix: str = ""
) -> str:
    path_name = unquote(Path(urlsplit(url).path).name) or "asset"
    if not Path(path_name).suffix:
        path_name += fallback_suffix
    path_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", path_name).rstrip(" .")
    if not path_name:
        path_name = "asset"
    stem = Path(path_name).stem or "asset"
    suffix = Path(path_name).suffix
    if re.fullmatch(r"(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])", stem):
        stem = f"_{stem}"
        path_name = f"{stem}{suffix}"
    candidate = path_name
    if candidate.casefold() in occupied:
        digest = hashlib.sha256(canonicalize_url(url).encode("utf-8")).hexdigest()[:8]
        candidate = f"{stem}-{digest}{suffix}"
    occupied.add(candidate.casefold())
    return candidate


class WikiCrawler:
    """Discover and snapshot a wiki graph using an injected fetcher."""

    def __init__(
        self,
        *,
        fetcher=fetch_url,
        cache_root: Path | None = None,
        robots_policy: RobotsPolicy | None = None,
    ):
        self.fetcher = fetcher
        self.cache_root = cache_root
        self.robots_policy = robots_policy or RobotsPolicy()

    def crawl(
        self,
        start_url: str,
        root_url: str,
        scope: str,
        *,
        respect_robots_txt: bool = True,
        download_assets: bool = False,
        cancel_event: threading.Event | None = None,
        progress=None,
    ) -> tuple[WikiImport, list[str]]:
        if scope not in {"whole", "subwiki"}:
            raise ValueError("Wiki scope must be 'whole' or 'subwiki'")

        cancel_event = cancel_event or threading.Event()
        start_navigation_url = canonicalize_url(start_url, keep_fragment=True)
        start_identity = canonicalize_url(start_url)
        root = canonicalize_url(root_url)
        if not is_within_root(start_identity, root):
            raise ValueError("Starting page is outside the selected wiki root")

        import_id = str(uuid.uuid4())
        cache_dir = self.cache_root or get_wiki_cache_directory(import_id)
        pages_dir = cache_dir / "pages"
        assets_dir = cache_dir / "assets"
        pages_dir.mkdir(parents=True, exist_ok=True)

        queue = deque([(start_navigation_url, start_identity)])
        queued = {start_identity}
        visited: set[str] = set()
        pages: list[WikiPage] = []
        pages_by_canonical: dict[str, WikiPage] = {}
        warnings: list[str] = []
        asset_candidates: dict[str, str] = {}

        while queue and not cancel_event.is_set():
            original_url, requested_identity = queue.popleft()
            if requested_identity in visited:
                continue
            visited.add(requested_identity)
            if respect_robots_txt and not self.robots_policy.can_fetch(requested_identity):
                warnings.append(f"Blocked by robots.txt: {requested_identity}")
                continue

            if progress:
                progress(
                    f"Discovering page {len(visited)}; {len(queue)} queued: "
                    f"{requested_identity}"
                )

            try:
                response = self.fetcher(requested_identity)
                final_url = canonicalize_url(response.final_url)
                if not is_within_root(final_url, root):
                    raise ValueError("Redirect left the selected wiki root")
                if (
                    scope == "subwiki"
                    and requested_identity != start_identity
                    and final_url != requested_identity
                    and not should_follow_subwiki_link(
                        start_identity, requested_identity, final_url
                    )
                ):
                    raise ValueError("Redirect left the selected sub-wiki boundary")
                existing_page = pages_by_canonical.get(final_url)
                if existing_page:
                    if original_url not in existing_page.aliases:
                        existing_page.aliases.append(original_url)
                    continue
                if response.content_type not in {"text/html", "application/xhtml+xml"}:
                    raise ValueError(f"Not an HTML page ({response.content_type})")

                soup = BeautifulSoup(response.body, "html.parser")
                outgoing_urls: list[str] = []
                page_asset_urls: list[str] = []

                for tag in soup.find_all(href=True):
                    raw_link = str(tag.get("href", "")).strip()
                    if not raw_link:
                        continue
                    try:
                        navigable = resolve_url(final_url, raw_link, keep_fragment=True)
                        identity = canonicalize_url(navigable)
                    except ValueError:
                        continue
                    tag["data-docling-absolute-href"] = navigable

                    if not _looks_like_page(identity):
                        if download_assets:
                            asset_candidates.setdefault(identity, navigable)
                            if identity not in page_asset_urls:
                                page_asset_urls.append(identity)
                        continue

                    in_scope = (
                        is_within_root(identity, root)
                        if scope == "whole"
                        else should_follow_subwiki_link(
                            start_identity, final_url, identity
                        )
                    )
                    if not in_scope:
                        continue
                    if identity not in outgoing_urls:
                        outgoing_urls.append(identity)
                    if identity not in queued and identity not in visited:
                        queue.append((navigable, identity))
                        queued.add(identity)

                for tag in soup.find_all(src=True):
                    raw_source = str(tag.get("src", "")).strip()
                    if not raw_source:
                        continue
                    try:
                        navigable = resolve_url(final_url, raw_source, keep_fragment=True)
                        identity = canonicalize_url(navigable)
                    except ValueError:
                        continue
                    tag["data-docling-absolute-src"] = navigable
                    if download_assets:
                        asset_candidates.setdefault(identity, navigable)
                        if identity not in page_asset_urls:
                            page_asset_urls.append(identity)

                snapshot_bytes = str(soup).encode("utf-8")
                digest = hashlib.sha256(snapshot_bytes).hexdigest()
                snapshot_key = f"pages/{digest}.html"
                (cache_dir / snapshot_key).write_bytes(snapshot_bytes)
                page_id = str(uuid.uuid5(uuid.UUID(import_id), final_url))
                page = WikiPage(
                    id=page_id,
                    import_id=import_id,
                    original_url=original_url,
                    canonical_url=final_url,
                    fetched_at=response.fetched_at,
                    relative_path=relative_wiki_path(final_url, root),
                    output_filename=flattened_output_filename(final_url, root),
                    outgoing_urls=outgoing_urls,
                    asset_urls=page_asset_urls,
                    aliases=(
                        [original_url]
                        if canonicalize_url(original_url) != final_url
                        else []
                    ),
                    snapshot_key=snapshot_key,
                    content_hash=digest,
                )
                pages.append(page)
                pages_by_canonical[final_url] = page
            except Exception as exc:
                warnings.append(f"{requested_identity}: {exc}")

        if cancel_event.is_set():
            warnings.append("Discovery cancelled; partial results retained.")

        names = plan_output_filenames(
            [page.canonical_url for page in pages], root, ".md"
        )
        for page in pages:
            page.output_filename = names[page.canonical_url]

        assets: list[WikiAsset] = []
        if download_assets and not cancel_event.is_set():
            assets_dir.mkdir(parents=True, exist_ok=True)
            occupied_names: set[str] = set()
            total_bytes = 0
            for identity, original_url in asset_candidates.items():
                if cancel_event.is_set():
                    break
                try:
                    response = self.fetcher(identity)
                    total_bytes += len(response.body)
                    if total_bytes > MAX_ASSET_TOTAL_BYTES:
                        warnings.append("Asset download total limit reached.")
                        break
                    digest = hashlib.sha256(response.body).hexdigest()
                    suffix = Path(urlsplit(identity).path).suffix
                    if not suffix:
                        suffix = mimetypes.guess_extension(response.content_type) or ""
                    output_name = _safe_asset_filename(
                        response.final_url, occupied_names, suffix
                    )
                    snapshot_key = f"assets/{digest}{suffix}"
                    (cache_dir / snapshot_key).write_bytes(response.body)
                    assets.append(
                        WikiAsset(
                            original_url=original_url,
                            canonical_url=canonicalize_url(response.final_url),
                            fetched_at=response.fetched_at,
                            snapshot_key=snapshot_key,
                            content_hash=digest,
                            output_filename=output_name,
                        )
                    )
                except Exception as exc:
                    warnings.append(f"Asset {identity}: {exc}")

        wiki_import = WikiImport(
            id=import_id,
            start_url=start_navigation_url,
            root_url=root,
            scope=scope,
            respect_robots_txt=respect_robots_txt,
            download_assets=download_assets,
            pages=pages,
            assets=assets,
            discovered_at=_utc_now(),
        )
        manifest = {
            "wiki_import": wiki_import.to_dict(),
            "warnings": warnings,
        }
        manifest_path = cache_dir / "manifest.json"
        temporary_manifest = cache_dir / "manifest.json.tmp"
        temporary_manifest.write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        temporary_manifest.replace(manifest_path)
        return wiki_import, warnings


class WikiDiscoveryWorker(QThread):
    """Run wiki discovery without blocking the GUI thread."""

    progress = Signal(str)
    result_ready = Signal(object, object)
    failed = Signal(str)

    def __init__(
        self,
        start_url: str,
        root_url: str,
        scope: str,
        respect_robots_txt: bool,
        download_assets: bool,
    ):
        super().__init__()
        self.start_url = start_url
        self.root_url = root_url
        self.scope = scope
        self.respect_robots_txt = respect_robots_txt
        self.download_assets = download_assets
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        try:
            wiki_import, warnings = WikiCrawler().crawl(
                self.start_url,
                self.root_url,
                self.scope,
                respect_robots_txt=self.respect_robots_txt,
                download_assets=self.download_assets,
                cancel_event=self._cancel_event,
                progress=self.progress.emit,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.result_ready.emit(wiki_import, warnings)
