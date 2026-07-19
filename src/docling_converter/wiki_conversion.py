"""Wiki conversion helpers and worker."""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import tempfile
import warnings
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup
from PySide6.QtCore import QThread, Signal

from docling_converter.conversion_logic import (
    FORMAT_OPTIONS,
    ConversionWorker,
    _export_document,
    _severity_icon,
)
from docling_converter.wiki_model import WikiAsset, WikiImport, WikiPage
from docling_converter.wiki_urls import canonicalize_url, plan_output_filenames
from docling_converter.workspace_paths import get_wiki_cache_directory


def add_markdown_provenance(
    content: str, original_url: str, fetched_at: str
) -> str:
    """Prepend YAML-compatible provenance using safely quoted JSON strings."""

    frontmatter = "\n".join(
        (
            "---",
            f"original_url: {json.dumps(original_url, ensure_ascii=False)}",
            f"fetched_at: {json.dumps(fetched_at, ensure_ascii=False)}",
            "---",
            "",
        )
    )
    return frontmatter + content.lstrip("\ufeff")


def add_html_provenance(content: str, original_url: str, fetched_at: str) -> str:
    """Prepend provenance in a valid HTML comment."""

    safe_url = html.escape(original_url, quote=True).replace("--", "&#45;&#45;")
    safe_timestamp = html.escape(fetched_at, quote=True).replace("--", "&#45;&#45;")
    comment = (
        "<!--\n"
        f"original_url: {safe_url}\n"
        f"fetched_at: {safe_timestamp}\n"
        "-->\n"
    )
    return comment + content.lstrip("\ufeff")


def verify_snapshot(page: WikiPage, cache_dir: Path) -> Path:
    """Resolve and verify a page snapshot without allowing cache traversal."""

    cache_root = cache_dir.resolve()
    snapshot = (cache_root / page.snapshot_key).resolve()
    if cache_root not in snapshot.parents:
        raise ValueError(f"Unsafe snapshot path for {page.original_url}")
    if not snapshot.is_file():
        raise FileNotFoundError(f"Missing cached snapshot for {page.original_url}")
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    if digest != page.content_hash:
        raise ValueError(f"Cached snapshot changed for {page.original_url}")
    return snapshot


def _prepare_snapshot_html(
    page: WikiPage,
    snapshot_path: Path,
) -> Path:
    html_text = snapshot_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_text, "html.parser")

    for tag in soup.find_all(href=True):
        absolute_url = tag.get("data-docling-absolute-href", "")
        if absolute_url:
            tag["href"] = absolute_url
            del tag["data-docling-absolute-href"]

    for tag in soup.find_all(src=True):
        absolute_url = tag.get("data-docling-absolute-src", "")
        if absolute_url:
            tag["src"] = absolute_url
            del tag["data-docling-absolute-src"]

    temp_file = tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".html", encoding="utf-8"
    )
    with temp_file:
        temp_file.write(str(soup))
    return Path(temp_file.name)


def _plan_asset_targets(
    wiki_imports: list[WikiImport], allowed_urls: set[str]
) -> dict[str, str]:
    targets: dict[str, str] = {}
    occupied: set[str] = set()
    for wiki_import in sorted(wiki_imports, key=lambda item: item.id):
        if not wiki_import.download_assets:
            continue
        for asset in sorted(wiki_import.assets, key=lambda item: item.canonical_url):
            identity = canonicalize_url(asset.canonical_url)
            if identity not in allowed_urls:
                continue
            if identity in targets:
                continue
            candidate = asset.output_filename
            if candidate.casefold() in occupied:
                digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8]
                candidate = f"{Path(candidate).stem}-{digest}{Path(candidate).suffix}"
            occupied.add(candidate.casefold())
            targets[identity] = candidate
    return targets


def _copy_assets(
    wiki_imports: list[WikiImport],
    output_dir: Path,
    planned_targets: dict[str, str],
) -> tuple[dict[str, str], list[str]]:
    messages: list[str] = []
    assets_dir = output_dir / "assets"
    successful_targets: dict[str, str] = {}
    copied: set[str] = set()

    for wiki_import in wiki_imports:
        if not wiki_import.download_assets:
            continue
        cache_dir = get_wiki_cache_directory(wiki_import.id)
        for asset in wiki_import.assets:
            identity = canonicalize_url(asset.canonical_url)
            if identity not in planned_targets:
                continue
            if identity in copied:
                continue
            try:
                source = _verified_asset_path(asset, cache_dir)
                assets_dir.mkdir(parents=True, exist_ok=True)
                target_name = planned_targets[identity]
                shutil.copy2(source, assets_dir / target_name)
                copied.add(identity)
                successful_targets[identity] = target_name
                successful_targets[canonicalize_url(asset.original_url)] = target_name
            except Exception as exc:
                messages.append(f"Asset {asset.original_url}: {exc}")
    return successful_targets, messages


def _verified_asset_path(asset: WikiAsset, cache_dir: Path) -> Path:
    cache_root = cache_dir.resolve()
    source = (cache_root / asset.snapshot_key).resolve()
    if cache_root not in source.parents or not source.is_file():
        raise FileNotFoundError("cached asset is missing")
    if hashlib.sha256(source.read_bytes()).hexdigest() != asset.content_hash:
        raise ValueError("cached asset changed")
    return source


def _target_for_url(url: str, targets: dict[str, str]) -> str | None:
    try:
        parts = urlsplit(url)
        identity = canonicalize_url(url)
    except ValueError:
        return None
    target = targets.get(identity)
    if not target:
        return None
    return f"{target}#{parts.fragment}" if parts.fragment else target


def rewrite_html_links(
    content: str,
    page_targets: dict[str, str],
    asset_targets: dict[str, str],
) -> str:
    """Rewrite exported HTML links using successful page and asset maps."""

    soup = BeautifulSoup(content, "html.parser")
    for tag in soup.find_all(href=True):
        href = str(tag["href"])
        target = _target_for_url(href, page_targets)
        if target:
            tag["href"] = target
            continue
        asset = _target_for_url(href, asset_targets)
        if asset:
            tag["href"] = f"assets/{asset}"
    for tag in soup.find_all(src=True):
        source = str(tag["src"])
        asset = _target_for_url(source, asset_targets)
        if asset:
            tag["src"] = f"assets/{asset}"
    return str(soup)


_REFERENCE_DESTINATION = re.compile(
    r"(?P<prefix>^\s{0,3}\[[^\]\n]+\]:\s*)(?P<url>https?://\S+)(?P<suffix>\s*)$"
)
_AUTOLINK = re.compile(r"<(?P<url>https?://[^>\s]+)>")


def _rewrite_inline_destinations(
    segment: str,
    page_targets: dict[str, str],
    asset_targets: dict[str, str],
) -> str:
    output: list[str] = []
    position = 0
    while True:
        marker = segment.find("](", position)
        if marker < 0:
            output.append(segment[position:])
            break
        destination_start = marker + 2
        while (
            destination_start < len(segment)
            and segment[destination_start].isspace()
        ):
            destination_start += 1
        output.append(segment[position:destination_start])

        wrapped = (
            destination_start < len(segment)
            and segment[destination_start] == "<"
        )
        url_start = destination_start + 1 if wrapped else destination_start
        if not segment.startswith(("http://", "https://"), url_start):
            position = destination_start
            continue

        if wrapped:
            url_end = segment.find(">", url_start)
            if url_end < 0:
                position = destination_start
                continue
        else:
            depth = 1
            url_end = url_start
            while url_end < len(segment):
                character = segment[url_end]
                if character == "\\":
                    url_end += 2
                    continue
                if character == "(":
                    depth += 1
                elif character == ")":
                    depth -= 1
                    if depth == 0:
                        break
                elif character.isspace() and depth == 1:
                    break
                url_end += 1

        url = segment[url_start:url_end]
        target = _target_for_url(url, page_targets)
        if not target:
            asset = _target_for_url(url, asset_targets)
            target = f"assets/{asset}" if asset else None
        if target:
            if wrapped:
                output.append(f"<{target}>")
                position = url_end + 1
            else:
                output.append(target)
                position = url_end
        else:
            position = destination_start
    return "".join(output)


def rewrite_markdown_links(
    content: str,
    page_targets: dict[str, str],
    asset_targets: dict[str, str],
) -> str:
    """Rewrite Markdown destinations while skipping fenced and inline code."""

    def replacement(match) -> str:
        url = match.group("url")
        target = _target_for_url(url, page_targets)
        if not target:
            asset = _target_for_url(url, asset_targets)
            target = f"assets/{asset}" if asset else None
        if not target:
            return match.group(0)
        groups = match.groupdict()
        if "prefix" in groups:
            return f"{groups['prefix']}{target}{groups['suffix']}"
        return f"<{target}>"

    output_lines: list[str] = []
    in_fence = False
    fence_marker = ""
    for line in content.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
            output_lines.append(line)
            continue
        if in_fence:
            output_lines.append(line)
            continue

        segments = re.split(r"(`+[^`]*`+)", line)
        for index in range(0, len(segments), 2):
            segment = _rewrite_inline_destinations(
                segments[index], page_targets, asset_targets
            )
            segment = _REFERENCE_DESTINATION.sub(replacement, segment)
            segment = _AUTOLINK.sub(replacement, segment)
            segments[index] = segment
        output_lines.append("".join(segments))
    return "".join(output_lines)


def _plan_batch_names(
    wiki_imports: list[WikiImport],
    pages: list[WikiPage],
    extension: str | dict[str, str],
) -> dict[str, str]:
    pages_by_import: dict[str, list[WikiPage]] = {}
    for page in pages:
        pages_by_import.setdefault(page.import_id, []).append(page)

    planned: dict[str, str] = {}
    occupied: set[str] = set()
    imports_by_id = {item.id: item for item in wiki_imports}
    for import_id in sorted(pages_by_import):
        wiki_import = imports_by_id[import_id]
        import_pages = pages_by_import[import_id]
        local_names: dict[str, str] = {}
        pages_by_extension: dict[str, list[WikiPage]] = {}
        for page in import_pages:
            page_extension = (
                extension.get(page.canonical_url, ".md")
                if isinstance(extension, dict)
                else extension
            )
            pages_by_extension.setdefault(page_extension, []).append(page)
        for page_extension, extension_pages in pages_by_extension.items():
            local_names.update(
                plan_output_filenames(
                    [page.canonical_url for page in extension_pages],
                    wiki_import.root_url,
                    page_extension,
                )
            )
        for page in sorted(import_pages, key=lambda item: item.canonical_url):
            candidate = local_names[page.canonical_url]
            if candidate.casefold() in occupied:
                stem = Path(candidate).stem
                suffix = Path(candidate).suffix
                digest = hashlib.sha256(
                    page.canonical_url.encode("utf-8")
                ).hexdigest()[:8]
                candidate = f"{stem}-{digest}{suffix}"
            occupied.add(candidate.casefold())
            planned[page.canonical_url] = candidate
    return planned


class WikiConversionWorker(QThread):
    """Convert cached wiki pages and any ordinary queued sources."""

    progress = Signal(str)
    result_ready = Signal(object, str)

    def __init__(
        self,
        sources: list,
        wiki_imports: list[WikiImport],
        output_dir: Path,
        fmt_info: dict,
        custom_filename: str,
        source_formats: dict[str, str] | None = None,
    ):
        super().__init__()
        self.sources = sources
        self.wiki_imports = wiki_imports
        self.output_dir = output_dir
        self.fmt_info = fmt_info
        self.custom_filename = custom_filename
        self.source_formats = source_formats or {}

    def run(self):
        page_lookup: dict[str, WikiPage] = {}
        for wiki_import in self.wiki_imports:
            for page in wiki_import.pages:
                if page.included:
                    page_lookup[page.original_url] = page
                    page_lookup[page.canonical_url] = page
                    for alias in page.aliases:
                        page_lookup[alias] = page

        selected_pages: list[WikiPage] = []
        regular_sources: list = []
        selected_ids: set[str] = set()
        for source in self.sources:
            page = page_lookup.get(str(source))
            if page and page.id not in selected_ids:
                selected_pages.append(page)
                selected_ids.add(page.id)
            else:
                regular_sources.append(source)

        rows: list[dict] = []
        previews: list[str] = []
        if regular_sources:
            regular_payload: dict = {}
            regular_preview: list[str] = []
            worker = ConversionWorker(
                regular_sources,
                self.output_dir,
                self.fmt_info,
                self.custom_filename if not selected_pages else "",
                self.source_formats,
            )
            worker.progress.connect(self.progress.emit)
            worker.result_ready.connect(
                lambda payload, preview: (
                    regular_payload.update(payload),
                    regular_preview.append(preview),
                )
            )
            worker.run()
            rows.extend(regular_payload.get("rows", []))
            previews.extend(regular_preview)

        if selected_pages:
            from docling.document_converter import DocumentConverter

            page_formats = {}
            for page in selected_pages:
                format_label = next(
                    (
                        self.source_formats[source]
                        for source in (
                            page.original_url,
                            page.canonical_url,
                            *page.aliases,
                        )
                        if source in self.source_formats
                    ),
                    "",
                )
                page_formats[page.canonical_url] = FORMAT_OPTIONS.get(
                    format_label, self.fmt_info
                )
            extensions = {
                url: format_info["ext"]
                for url, format_info in page_formats.items()
            }
            planned = _plan_batch_names(
                self.wiki_imports, selected_pages, extensions
            )
            import_lookup = {item.id: item for item in self.wiki_imports}
            converted: list[
                tuple[WikiPage, Path, str, str, list[str], str]
            ] = []
            temp_dir = Path(tempfile.mkdtemp(prefix="docling_wiki_outputs_"))
            converter = DocumentConverter()
            try:
                for index, page in enumerate(selected_pages, 1):
                    target_name = planned[page.canonical_url]
                    self.progress.emit(
                        f"Converting wiki page {index}/{len(selected_pages)}: "
                        f"{page.original_url}"
                    )
                    prepared_path: Path | None = None
                    try:
                        wiki_import = import_lookup[page.import_id]
                        key = page_formats[page.canonical_url]["key"]
                        cache_dir = get_wiki_cache_directory(wiki_import.id)
                        snapshot = verify_snapshot(page, cache_dir)
                        prepared_path = _prepare_snapshot_html(page, snapshot)
                        with warnings.catch_warnings(record=True) as captured:
                            warnings.simplefilter("always")
                            result = converter.convert(str(prepared_path))
                        messages = [str(item.message) for item in captured]
                        result_errors = list(getattr(result, "errors", []) or [])
                        messages.extend(str(item) for item in result_errors)
                        result_status = str(getattr(result, "status", "")).lower()
                        if result_errors and any(
                            token in result_status
                            for token in ("fail", "fatal", "error")
                        ):
                            raise RuntimeError("; ".join(messages))
                        severity = (
                            "warning"
                            if messages
                            or any(
                                token in result_status
                                for token in ("warn", "partial")
                            )
                            else "success"
                        )
                        content = _export_document(result.document, key)
                        temp_output = temp_dir / target_name
                        temp_output.write_text(content, encoding="utf-8")
                        converted.append(
                            (
                                page,
                                temp_output,
                                target_name,
                                severity,
                                messages,
                                key,
                            )
                        )
                    except Exception as exc:
                        rows.append(
                            {
                                "severity": "error",
                                "source": page.original_url,
                                "target": "",
                                "messages": [str(exc)],
                            }
                        )
                    finally:
                        if prepared_path:
                            prepared_path.unlink(missing_ok=True)

                successful_targets: dict[str, str] = {}
                for (
                    page,
                    _temp_path,
                    target_name,
                    _severity,
                    _messages,
                    _key,
                ) in converted:
                    successful_targets[canonicalize_url(page.original_url)] = target_name
                    successful_targets[page.canonical_url] = target_name
                    for alias in page.aliases:
                        successful_targets[canonicalize_url(alias)] = target_name

                selected_import_ids = {page.import_id for page in selected_pages}
                selected_imports = [
                    item
                    for item in self.wiki_imports
                    if item.id in selected_import_ids
                ]
                selected_asset_urls = {
                    canonicalize_url(url)
                    for page in selected_pages
                    for url in page.asset_urls
                }
                planned_asset_targets = _plan_asset_targets(
                    selected_imports, selected_asset_urls
                )
                asset_targets, asset_messages = _copy_assets(
                    selected_imports, self.output_dir, planned_asset_targets
                )
                for (
                    page,
                    temp_output,
                    target_name,
                    severity,
                    messages,
                    key,
                ) in converted:
                    try:
                        content = temp_output.read_text(encoding="utf-8")
                        if key == "markdown":
                            content = rewrite_markdown_links(
                                content, successful_targets, asset_targets
                            )
                            content = add_markdown_provenance(
                                content, page.original_url, page.fetched_at
                            )
                        else:
                            content = rewrite_html_links(
                                content, successful_targets, asset_targets
                            )
                            content = add_html_provenance(
                                content, page.original_url, page.fetched_at
                            )
                        (self.output_dir / target_name).write_text(
                            content, encoding="utf-8"
                        )
                        rows.append(
                            {
                                "severity": (
                                    "warning"
                                    if severity == "warning" or asset_messages
                                    else "success"
                                ),
                                "source": page.original_url,
                                "target": target_name,
                                "messages": [*messages, *asset_messages],
                            }
                        )
                        if not previews:
                            previews.append(content)
                    except Exception as exc:
                        rows.append(
                            {
                                "severity": "error",
                                "source": page.original_url,
                                "target": "",
                                "messages": [str(exc)],
                            }
                        )
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        summary_lines = [
            f"{_severity_icon(row['severity'])}  {row['source']}  ->  "
            f"{row['target'] or '(failed)'}"
            for row in rows
        ]
        payload = {
            "rows": rows,
            "summary": "\n".join(summary_lines),
            "has_errors": any(row["severity"] == "error" for row in rows),
            "output_dir": str(self.output_dir),
        }
        self.result_ready.emit(payload, previews[0] if previews else "")


def planned_wiki_conflicts(
    sources: list[str],
    wiki_imports: list[WikiImport],
    output_dir: Path,
    extension: str,
    source_formats: dict[str, str] | None = None,
) -> list[Path]:
    """Return all existing paths a wiki batch would overwrite."""

    source_set = set(sources)
    pages = [
        page
        for wiki_import in wiki_imports
        for page in wiki_import.pages
        if page.included
        and (
            page.original_url in source_set
            or page.canonical_url in source_set
            or bool(source_set.intersection(page.aliases))
        )
    ]
    source_formats = source_formats or {}
    extensions = {}
    for page in pages:
        format_label = next(
            (
                source_formats[source]
                for source in (page.original_url, page.canonical_url, *page.aliases)
                if source in source_formats
            ),
            "",
        )
        extensions[page.canonical_url] = FORMAT_OPTIONS.get(
            format_label, {"ext": extension}
        )["ext"]
    names = _plan_batch_names(wiki_imports, pages, extensions)
    conflicts = {
        path
        for path in (output_dir / names[page.canonical_url] for page in pages)
        if path.exists()
    }
    selected_import_ids = {page.import_id for page in pages}
    selected_imports = [
        item for item in wiki_imports if item.id in selected_import_ids
    ]
    selected_asset_urls = {
        canonicalize_url(url) for page in pages for url in page.asset_urls
    }
    for target_name in _plan_asset_targets(
        selected_imports, selected_asset_urls
    ).values():
        asset_path = output_dir / "assets" / target_name
        if asset_path.exists():
            conflicts.add(asset_path)
    return sorted(conflicts)
