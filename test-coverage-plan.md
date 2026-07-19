# Test Coverage Expansion Plan

## Goal

Close the gaps listed in `TEST.md`'s "Not Covered by Unit Tests" section for
native dialog UX, drag-and-drop, and other interactive GUI flows. This is
ongoing, not a one-shot task: as new interactive surface area ships, it should
get automated coverage using the patterns below instead of silently joining
the manual-only list.

## Current State

- The test suite uses a session-scoped `qapp` fixture (`QApplication` with
  `QT_QPA_PLATFORM=offscreen`) plus `monkeypatch` to substitute internal
  helper functions (e.g. `_get_downloads_directory`, `ConversionWorker`)
  rather than exercising real Qt dialogs or drag/drop events.
- `FileDropTextEdit` (`main.py`) has real `dragEnterEvent`/`dragMoveEvent`/
  `dropEvent` handlers that are entirely untested. Dropped local file paths
  and remote URLs take different branches (`url.toLocalFile()` vs
  `url.toString()`) that diverge in behavior and aren't verified either way.
- Eight call sites use `QFileDialog.getOpenFileNames` /
  `getOpenFileName` / `getExistingDirectory` / `getSaveFileName` across
  `main.py` and `workspace_ui.py` — none are patched to verify what the app
  does with the dialog's return value, including the cancel case (PySide
  returns an empty string/list, not `None`).
- No `pytest-qt` dependency. `QTest` (from `PySide6.QtTest`) is already
  available through the installed `pyside6` package if synthetic
  mouse/keyboard events are ever needed — no new dependency required for
  anything in this plan.

## Approach

### Drag-and-drop

Construct real `QDropEvent`/`QDragEnterEvent` objects with a `QMimeData`
carrying `QUrl` entries (local file paths, and separately a plain web URL)
and dispatch them directly against a `FileDropTextEdit` instance — no real OS
drag, no `pytest-qt` needed. Assert on the resulting `toPlainText()` for: an
empty widget, appending to existing content, multiple URLs in one drop, and a
drop with `hasUrls() == False` (falls through to the base class handler and
should be a no-op for app purposes).

### Native dialogs

The dialog call itself is the boundary, not business logic worth testing in
isolation. Test the surrounding handler with
`monkeypatch.setattr(main.QFileDialog, "getOpenFileNames", lambda *a, **kw: (["a.pdf", "b.pdf"], ""))`
(and the equivalent for each other dialog method), matching the existing
`monkeypatch`-heavy style already used in `test_main.py` rather than adding
`pytest-qt`. Cover, per call site: a normal selection, and the cancel case
(empty return value) leaving state unchanged.

### Broader interactive GUI flows

For flows that span more than one dialog call — the wiki-import dialog's
root-confirmation step, the overwrite-conflict prompt, discovery cancellation
mid-crawl — call the handler methods and emit signals directly against the
`qapp`-backed widgets rather than simulating mouse clicks. Only reach for
`QTest.mouseClick`/`keyClick` where a handler is genuinely only reachable
through a real widget event (e.g. confirming a button is actually wired to a
slot, not re-testing logic the slot test already covers).

## Ongoing Checklist

Track progress here rather than in `PENDING_TASKS.md`; check items off as
coverage is added, and add new rows as new interactive surface area ships
instead of letting it silently join `TEST.md`'s manual-only list.

- [ ] `FileDropTextEdit` drag-and-drop: local file path(s), remote URL, mixed,
      appending to existing content, non-URL mime data no-op
- [ ] `QFileDialog.getOpenFileNames` call sites (file/wiki-asset add paths in
      `main.py`): normal selection, cancel/empty
- [ ] `QFileDialog.getExistingDirectory` call sites (target dir, output dir,
      workspace base dir in `main.py`/`workspace_ui.py`): normal selection,
      cancel/empty
- [ ] `QFileDialog.getOpenFileName` / `getSaveFileName` (workspace open/save):
      normal selection, cancel/empty
- [ ] Add Wiki dialog: root-confirmation flow when the inferred root differs
      from the supplied URL, and cancel
- [ ] Overwrite-conflict prompt: confirmation applies to the full displayed
      set, cancel performs no writes
- [ ] Discovery cancellation mid-crawl: worker thread teardown, partial
      results retained
- [ ] App close while a discovery/conversion worker is running (existing
      worker-cleanup tests cover some of this — confirm and extend rather
      than duplicate)

## Non-goals

- Adding `pytest-qt` or any new GUI test dependency — the existing `qapp` +
  `monkeypatch` + direct-event-construction pattern covers everything listed
  above.
- Real OS-level drag-and-drop or screenshot-based testing — synthetic Qt
  events at the widget-API level are the right fidelity for this app.
- Real Docling conversion execution, OCR/model backend behavior, and
  first-run model downloads stay manual-only per `TEST.md` — those aren't
  dialog/drag-and-drop/GUI-flow gaps, so they're out of scope here.

## References

- `TEST.md` — "Not Covered by Unit Tests"
- `tests/test_main.py` — existing `qapp`/`monkeypatch` conventions to follow
