from docling_converter.workspace_model import (
    ConvertedItem,
    VlmSettings,
    WorkspaceData,
    WorkspaceSettings,
)
from docling_converter.wiki_model import WikiAsset, WikiImport, WikiPage


def test_vlm_settings_defaults():
    assert VlmSettings() == VlmSettings(
        enabled=False,
        api_url="http://localhost:11434/v1/chat/completions",
        model="granite3.2-vision:2b",
        api_key="",
    )


def test_vlm_settings_round_trip():
    vlm_settings = VlmSettings(
        enabled=True,
        api_url="https://api.example.com/v1/chat/completions",
        model="some-other-vision-model",
        api_key="secret",
    )

    assert VlmSettings.from_dict(vlm_settings.to_dict()) == vlm_settings


def test_vlm_settings_from_dict_falls_back_to_defaults_for_blank_url_and_model():
    restored = VlmSettings.from_dict({"api_url": "  ", "model": ""})

    assert restored.api_url == "http://localhost:11434/v1/chat/completions"
    assert restored.model == "granite3.2-vision:2b"


def test_vlm_settings_from_dict_parses_string_enabled_values():
    assert VlmSettings.from_dict({"enabled": "false"}).enabled is False
    assert VlmSettings.from_dict({"enabled": "False"}).enabled is False
    assert VlmSettings.from_dict({"enabled": ""}).enabled is False
    assert VlmSettings.from_dict({"enabled": "0"}).enabled is False
    assert VlmSettings.from_dict({"enabled": "true"}).enabled is True
    assert VlmSettings.from_dict({"enabled": "1"}).enabled is True
    assert VlmSettings.from_dict({"enabled": True}).enabled is True
    assert VlmSettings.from_dict({"enabled": False}).enabled is False


def test_workspace_data_defaults_are_ui_safe():
    workspace = WorkspaceData()

    assert workspace.target_dir == ""
    assert workspace.pending_sources == []
    assert workspace.converted_items == []
    assert workspace.settings == WorkspaceSettings()


def test_workspace_data_round_trips_nested_state():
    workspace = WorkspaceData(
        label="Research",
        target_dir=r"C:\docs\output",
        pending_sources=[r"C:\docs\a.pdf", "https://example.com/page"],
        source_formats={
            r"C:\docs\a.pdf": "HTML (.html)",
            "https://example.com/page": "JSON (.json)",
        },
        converted_items=[
            ConvertedItem(
                source=r"C:\docs\a.pdf",
                target="a.md",
                severity="warning",
                messages=["OCR suggested"],
            )
        ],
        settings=WorkspaceSettings(
            format_label="JSON (.json)",
            custom_filename="bundle.json",
            auto_filename_enabled=False,
            vlm_settings=VlmSettings(
                enabled=True,
                api_url="https://api.example.com/v1/chat/completions",
                model="some-other-vision-model",
                api_key="secret",
            ),
        ),
    )

    restored = WorkspaceData.from_dict(workspace.to_dict())

    assert restored == workspace


def test_converted_item_from_dict_normalizes_message_values():
    item = ConvertedItem.from_dict(
        {
            "source": "https://example.com/doc",
            "target": "doc.md",
            "severity": "error",
            "messages": ["bad", 42],
        }
    )

    assert item.messages == ["bad", "42"]


def test_workspace_data_round_trips_wiki_graph():
    page = WikiPage(
        id="page-1",
        import_id="wiki-1",
        original_url="https://example.com/wiki/Page",
        canonical_url="https://example.com/wiki/Page",
        fetched_at="2026-07-12T18:00:00Z",
        relative_path="Page",
        output_filename="Page.md",
        outgoing_urls=["https://example.com/wiki/Other"],
        snapshot_key="pages/page-1.html",
        content_hash="abc",
    )
    asset = WikiAsset(
        original_url="https://example.com/image.png",
        canonical_url="https://example.com/image.png",
        fetched_at="2026-07-12T18:00:01Z",
        snapshot_key="assets/image.png",
        content_hash="def",
        output_filename="image.png",
    )
    workspace = WorkspaceData(
        pending_sources=[page.original_url],
        wiki_imports=[
            WikiImport(
                id="wiki-1",
                start_url=page.original_url,
                root_url="https://example.com/wiki/",
                scope="whole",
                pages=[page],
                assets=[asset],
                discovered_at="2026-07-12T18:00:02Z",
            )
        ],
    )

    restored = WorkspaceData.from_dict(workspace.to_dict())

    assert restored == workspace
    assert restored.find_wiki_page(page.original_url) == page
