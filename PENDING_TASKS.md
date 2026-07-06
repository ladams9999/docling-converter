# Pending Tasks for Docling Converter

Tasks below are intentionally small and individually pickable.

---

- Add helpers for the default home-based workspace location and workspace file
  paths.
- Extract workspace state/persistence and conversion orchestration out of the
  current monolithic `main.py` UI flow.
- Replace the single-screen window shell with tabs for **Settings**,
  **Workspace**, **Pending**, and **Converted**.
- Build the **Workspace** tab controls for source assignment, target directory
  selection, and workspace load/save actions.
- Build the **Pending** tab list and add/remove actions for files, directories,
  and single URLs.
- Add shared conversion-progress state that can be surfaced consistently across
  tabs.
- Build the **Converted** tab list for completed items and wire completion state
  into it.
- Reconnect the current worker/export flow so queued items convert correctly in
  the new workspace-based UI.
- Expand tests around workspace state, persistence, tab construction, queue
  behavior, and migrated conversion orchestration.
- Refresh `IMPLEMENTATION.md`, `README.md`, and `TEST.md` after the redesign
  lands.

- Extract `main.py` into focused modules once the current single-file structure
  becomes too costly to maintain.
- Expand coverage beyond the current unit tests for drag-and-drop behavior,
  native dialogs, and full interactive GUI flows.
- Add packaging and release documentation for distributing Docling Converter to
  non-developer desktop users.
