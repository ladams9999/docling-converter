"""Workspace state models for the tabbed application flow."""

from __future__ import annotations

from dataclasses import dataclass, field


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

    target_dir: str = ""
    pending_sources: list[str] = field(default_factory=list)
    converted_items: list[ConvertedItem] = field(default_factory=list)
    settings: WorkspaceSettings = field(default_factory=WorkspaceSettings)

    def to_dict(self) -> dict:
        return {
            "target_dir": self.target_dir,
            "pending_sources": list(self.pending_sources),
            "converted_items": [item.to_dict() for item in self.converted_items],
            "settings": self.settings.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkspaceData":
        return cls(
            target_dir=str(data.get("target_dir", "")),
            pending_sources=[str(item) for item in data.get("pending_sources", [])],
            converted_items=[
                ConvertedItem.from_dict(item)
                for item in data.get("converted_items", [])
            ],
            settings=WorkspaceSettings.from_dict(data.get("settings", {})),
        )
