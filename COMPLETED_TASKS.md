# Completed Tasks for Docling Converter

- Built a PySide6 desktop GUI for Docling-based document conversion.
- Added support for local files, directories of supported files, and HTTP/HTTPS
  document URLs as input sources.
- Added export support for Markdown, HTML, JSON, and DocTags output formats.
- Added automatic output filename generation with manual override and restore via
  the **Auto** button.
- Added automatic output-directory selection that prefers the first writable
  local source directory and falls back to the user's Downloads folder.
- Added an output-directory display row and an **Open output directory** action.
- Added a conversion results table with per-row status, source, target, and
  message tooltips.
- Added PDF chunking for large PDFs and recombination logic for Markdown, HTML,
  JSON, and DocTags outputs.
- Added unit coverage in `test_main.py` and a dedicated testing guide in
  `TEST.md`.
- Added a serializable workspace data model for target directory, pending
  sources, converted items, and workspace settings.
- Added versioned workspace save/load support with a clean JSON round-trip.
- Added default home-based workspace path helpers for the app root, default
  workspace, workspace file, and output directory.
- Extracted conversion orchestration and helper logic from `main.py` into a
  dedicated module while preserving the existing test seams.
- Replaced the single-screen shell with top-level **Settings**,
  **Workspace**, **Pending**, and **Converted** tabs as the new app frame.
- Added workspace-file state, save/load actions, and synchronized Workspace-tab
  controls for sources, target directory, and saved UI settings.
