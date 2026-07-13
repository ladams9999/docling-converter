"""Workspace state models for the tabbed application flow."""

from __future__ import annotations

from dataclasses import dataclass, field

from wiki_model import WikiImport, WikiPage


@dataclass(slots=True)
class ConvertedItem:
    """Represents a converted output tracked by the workspace."""

    source: str
    target: str
    severity: str = "success"
    messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "severity": self.severity,
            "messages": list(self.messages),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConvertedItem":
        return cls(
            source=str(data.get("source", "")),
            target=str(data.get("target", "")),
            severity=str(data.get("severity", "success")),
            messages=[str(item) for item in data.get("messages", [])],
        )


@dataclass(slots=True)
class WorkspaceSettings:
    """Stores workspace-scoped UI settings."""

    format_label: str = "Markdown (.md)"
    custom_filename: str = ""
    auto_filename_enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "format_label": self.format_label,
            "custom_filename": self.custom_filename,
            "auto_filename_enabled": self.auto_filename_enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkspaceSettings":
        return cls(
            format_label=str(data.get("format_label", "Markdown (.md)")),
            custom_filename=str(data.get("custom_filename", "")),
            auto_filename_enabled=bool(data.get("auto_filename_enabled", True)),
        )


@dataclass(slots=True)
class WorkspaceData:
    """Serializable workspace state."""

    label: str = "Default workspace"
    target_dir: str = ""
    pending_sources: list[str] = field(default_factory=list)
    source_formats: dict[str, str] = field(default_factory=dict)
    converted_items: list[ConvertedItem] = field(default_factory=list)
    settings: WorkspaceSettings = field(default_factory=WorkspaceSettings)
    wiki_imports: list[WikiImport] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "target_dir": self.target_dir,
            "pending_sources": list(self.pending_sources),
            "source_formats": dict(self.source_formats),
            "converted_items": [item.to_dict() for item in self.converted_items],
            "settings": self.settings.to_dict(),
            "wiki_imports": [item.to_dict() for item in self.wiki_imports],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkspaceData":
        return cls(
            label=str(data.get("label", "Default workspace")),
            target_dir=str(data.get("target_dir", "")),
            pending_sources=[str(item) for item in data.get("pending_sources", [])],
            source_formats={
                str(source): str(format_label)
                for source, format_label in data.get("source_formats", {}).items()
            },
            converted_items=[
                ConvertedItem.from_dict(item)
                for item in data.get("converted_items", [])
            ],
            settings=WorkspaceSettings.from_dict(data.get("settings", {})),
            wiki_imports=[
                WikiImport.from_dict(item) for item in data.get("wiki_imports", [])
            ],
        )

    def find_wiki_page(self, source: str) -> WikiPage | None:
        """Return the included wiki page represented by a pending source."""

        for wiki_import in self.wiki_imports:
            for page in wiki_import.pages:
                if page.included and source in (
                    page.original_url,
                    page.canonical_url,
                    *page.aliases,
                ):
                    return page
        return None
