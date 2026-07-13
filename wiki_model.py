"""Serializable models for discovered wiki imports."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class WikiAsset:
    """A downloaded asset associated with a wiki import."""

    original_url: str
    canonical_url: str
    fetched_at: str
    snapshot_key: str
    content_hash: str
    output_filename: str

    def to_dict(self) -> dict:
        return {
            "original_url": self.original_url,
            "canonical_url": self.canonical_url,
            "fetched_at": self.fetched_at,
            "snapshot_key": self.snapshot_key,
            "content_hash": self.content_hash,
            "output_filename": self.output_filename,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WikiAsset":
        return cls(
            original_url=str(data.get("original_url", "")),
            canonical_url=str(data.get("canonical_url", "")),
            fetched_at=str(data.get("fetched_at", "")),
            snapshot_key=str(data.get("snapshot_key", "")),
            content_hash=str(data.get("content_hash", "")),
            output_filename=str(data.get("output_filename", "")),
        )


@dataclass(slots=True)
class WikiPage:
    """A cached HTML page discovered during a wiki crawl."""

    id: str
    import_id: str
    original_url: str
    canonical_url: str
    fetched_at: str
    relative_path: str
    output_filename: str
    outgoing_urls: list[str] = field(default_factory=list)
    asset_urls: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    snapshot_key: str = ""
    content_hash: str = ""
    included: bool = True
    discovery_status: str = "discovered"
    status_message: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "import_id": self.import_id,
            "original_url": self.original_url,
            "canonical_url": self.canonical_url,
            "fetched_at": self.fetched_at,
            "relative_path": self.relative_path,
            "output_filename": self.output_filename,
            "outgoing_urls": list(self.outgoing_urls),
            "asset_urls": list(self.asset_urls),
            "aliases": list(self.aliases),
            "snapshot_key": self.snapshot_key,
            "content_hash": self.content_hash,
            "included": self.included,
            "discovery_status": self.discovery_status,
            "status_message": self.status_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WikiPage":
        return cls(
            id=str(data.get("id", "")),
            import_id=str(data.get("import_id", "")),
            original_url=str(data.get("original_url", "")),
            canonical_url=str(data.get("canonical_url", "")),
            fetched_at=str(data.get("fetched_at", "")),
            relative_path=str(data.get("relative_path", "")),
            output_filename=str(data.get("output_filename", "")),
            outgoing_urls=[str(item) for item in data.get("outgoing_urls", [])],
            asset_urls=[str(item) for item in data.get("asset_urls", [])],
            aliases=[str(item) for item in data.get("aliases", [])],
            snapshot_key=str(data.get("snapshot_key", "")),
            content_hash=str(data.get("content_hash", "")),
            included=bool(data.get("included", True)),
            discovery_status=str(data.get("discovery_status", "discovered")),
            status_message=str(data.get("status_message", "")),
        )


@dataclass(slots=True)
class WikiImport:
    """A discovered wiki graph and its cache policy."""

    id: str
    start_url: str
    root_url: str
    scope: str
    respect_robots_txt: bool = True
    download_assets: bool = False
    pages: list[WikiPage] = field(default_factory=list)
    assets: list[WikiAsset] = field(default_factory=list)
    discovered_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "start_url": self.start_url,
            "root_url": self.root_url,
            "scope": self.scope,
            "respect_robots_txt": self.respect_robots_txt,
            "download_assets": self.download_assets,
            "pages": [page.to_dict() for page in self.pages],
            "assets": [asset.to_dict() for asset in self.assets],
            "discovered_at": self.discovered_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WikiImport":
        return cls(
            id=str(data.get("id", "")),
            start_url=str(data.get("start_url", "")),
            root_url=str(data.get("root_url", "")),
            scope=str(data.get("scope", "whole")),
            respect_robots_txt=bool(data.get("respect_robots_txt", True)),
            download_assets=bool(data.get("download_assets", False)),
            pages=[WikiPage.from_dict(item) for item in data.get("pages", [])],
            assets=[WikiAsset.from_dict(item) for item in data.get("assets", [])],
            discovered_at=str(data.get("discovered_at", "")),
        )
