# Project plan for Docling Converter

## Project Overview

Docling Converter is a PySide6 desktop application that wraps
[Docling](https://github.com/docling-project/docling) in a native GUI. Users can
paste file paths or URLs, drag and drop files, browse with native dialogs, and
export supported documents to Markdown, HTML, JSON, or DocTags.

## Primary Goals

- Keep Docling Converter easy to run locally as a lightweight desktop utility.
- Preserve a responsive GUI while running potentially heavy document conversion
  work in the background.
- Support common document and image inputs with consistent export behavior
  across Markdown, HTML, JSON, and DocTags output.
- Keep the project approachable for contributors by documenting architecture,
  testing, and follow-up work clearly.

## Current Product Direction

- Maintain the PySide6 desktop workflow as the primary interface.
- Continue favoring a simple repository layout while documenting where the
  boundaries are if the app needs to be split into multiple modules.
- Preserve quality-of-life features already present in the app, including:
  - automatic output-directory selection
  - automatic output filename generation with manual override
  - conversion status reporting and results-table summaries
  - PDF chunking for large inputs

## Near-Term Priorities

- Keep the documentation set aligned with the actual code and tests.
- Strengthen confidence around desktop-specific flows that remain outside the
  current unit-test surface.
- Improve contributor guidance so future work can be picked up quickly.
