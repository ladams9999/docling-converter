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
- Added labeled workspace creation, a configurable base directory, per-input
  export formats, and a derived Output files list.
- Built the **Pending** tab queue with add/remove actions for files,
  directories, and single URLs, synchronized with workspace state.
- Added shared processing status and progress views so conversion state is
  visible from the Workspace, Pending, and Converted surfaces.
- Built the **Converted** tab history view and wired successful conversion
  results into persisted workspace state.
- Reconnected conversion start/completion to the workspace-backed pending queue,
  including queue draining for completed items.
- Expanded automated coverage for workspace state, persistence, tab
  construction, queue behavior, shared progress, converted history, and
  queue-based conversion orchestration.
- Refreshed `README.md`, `IMPLEMENTATION.md`, and `TEST.md` for the
  workspace-oriented tabbed workflow and current test surface.
- Added whole-wiki and sub-wiki discovery for public generic HTML sites with
  canonical loop detection, root confirmation, `robots.txt` policy, progress,
  cancellation, and persistent graph state.
- Added cached HTML snapshots, optional asset downloads, original URL and UTC
  fetch provenance, and version `1` workspace migration.
- Added deterministic flattened wiki filenames, linked Markdown/HTML batch
  conversion, successful-page link rewriting, and overwrite conflict
  confirmation.
- Added focused automated coverage for wiki URL rules, discovery, redirects,
  cache integrity, assets, provenance, conversion, and queue integration.
