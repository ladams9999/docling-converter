from workspace_model import ConvertedItem, WorkspaceData, WorkspaceSettings


def test_workspace_data_defaults_are_ui_safe():
    workspace = WorkspaceData()

    assert workspace.target_dir == ""
    assert workspace.pending_sources == []
    assert workspace.converted_items == []
    assert workspace.settings == WorkspaceSettings()


def test_workspace_data_round_trips_nested_state():
    workspace = WorkspaceData(
        target_dir=r"C:\docs\output",
        pending_sources=[r"C:\docs\a.pdf", "https://example.com/page"],
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
