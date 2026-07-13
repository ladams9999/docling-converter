# Wiki Import Implementation Plan

## Goal

Extend Docling Converter from single-page URL conversion to importing a
wiki-like collection of linked HTML pages. A user supplies any page in a wiki,
chooses **Whole wiki** or **Sub-wiki**, reviews and edits the discovered pages in
the **Pending** tab, and converts the selected pages to linked Markdown or HTML
files in one target directory.

For a source URL such as:

```text
https://example.com/wiki/a/subject/page.html
```

the output filename should be based on its path relative to the detected wiki
root:

```text
a-subject-page.md
```

Links between imported pages must point to the corresponding flattened Markdown
filenames.

## Current State

The current application already provides useful foundations:

- `main.py` owns the PySide6 tabs, pending queue, workspace synchronization, and
  conversion lifecycle.
- `conversion_logic.py` accepts local paths or individual HTTP/HTTPS URLs and
  creates one output per source in a background `ConversionWorker`.
- `WorkspaceData.pending_sources` persists pending items as plain strings.
- The **Pending** tab can add files, directories, and one URL at a time, then
  remove individual rows.
- Workspace persistence is versioned, but only version `1` is accepted.
- URL filenames currently use only the final URL path segment.
- There is no HTML crawl, URL canonicalization, page relationship model, wiki
  scope detection, page-selection metadata, crawl cancellation, or internal-link
  rewriting.

The plain-string pending model is the main constraint. A wiki page needs its
source URL, owning wiki import, relative wiki path, planned output filename, and
discovered outgoing wiki links to remain associated through review,
persistence, conversion, and history.

## Product Behavior

### Add Wiki Flow

1. Add an **Add wiki...** action to the **Workspace** and/or **Pending** source
   controls.
2. Open a dialog containing:
   - starting page URL
   - scope: **Whole wiki** or **Sub-wiki**
   - inferred wiki root, editable before discovery
   - **Respect robots.txt** option, enabled by default
   - **Download linked assets** choice, disabled by default
3. Validate the URL and root. When the inferred whole-wiki root differs from the
   supplied page URL, display both and require confirmation before discovery.
4. Start discovery on a background thread and snapshot fetched pages in the
   application cache.
5. Show discovery status and counts without blocking the GUI. Provide
   **Cancel** while discovery is running.
6. Add every successfully discovered page to **Pending** as an individually
   selectable row.
7. Let the user remove pages before conversion. A removed page remains in the
   wiki graph as excluded, and removal does not recursively exclude descendants.
8. Keep links to excluded or failed pages as their original absolute web URLs.
9. Before conversion, list all target-file conflicts and require the user to
   confirm overwriting all listed files or cancel the batch.
10. Convert all selected wiki pages to Markdown or HTML in the target directory
    and rewrite links only when the destination page is also included in the
    same conversion set.

The existing **Add URL** behavior remains a single-page conversion and must not
silently trigger a crawl.

### Scope Semantics

Use explicit, deterministic URL rules rather than page titles or visual
navigation position.

#### Whole Wiki

- Start from the supplied page but allow traversal to any crawlable page under
  the selected wiki root.
- Require the same normalized origin: scheme, hostname, and effective port.
- Require the normalized path to be under the selected wiki-root path prefix.
- Infer a root from the supplied URL. If it differs from the supplied URL,
  require the user to confirm or edit it before crawling.
- Traverse recursively until no new eligible pages remain. There is no page
  count limit; canonical visited-URL tracking prevents loops.

Example:

```text
Start:     https://example.com/docs/guides/install
Wiki root: https://example.com/docs/
Allowed:   https://example.com/docs/reference/config
Excluded:  https://example.com/blog/release
```

Initial root inference is deterministic:

- remove the query and fragment
- if the normalized path ends in `/`, use that URL as the inferred root
- otherwise, remove the final path segment and use its containing directory
- never infer a different origin

Thus `https://foundryvtt.com/api/v13/` remains its own root, while
`https://www.dandwiki.com/wiki/Hyrule_(5e_Campaign_Setting)` initially infers
`https://www.dandwiki.com/wiki/` and requires confirmation.

#### Sub-wiki

- Always include the supplied page. A `#fragment` focuses a heading but does not
  create a separate page identity or narrow the fetched document.
- Treat the supplied page's directory as the current directory.
- Recursively crawl linked pages whose paths are in directories below the
  current directory.
- Include one hop of pages linked directly from the starting page whose paths
  are in the current directory.
- Do not recursively follow same-directory links from those one-hop pages unless
  they lead into a child directory.
- Do not infer additional membership from incoming links, breadcrumbs, sidebar
  position, or MediaWiki categories in the first implementation.

This is the initial generic definition and may evolve as real wiki structures
are tested.

### Initial Site Targets

Target generic, public, authentication-free wiki-like HTML sites rather than a
single wiki engine. Representative acceptance sites include:

- `https://foundryvtt.com/api/v13/`
- `https://www.dandwiki.com/wiki/Hyrule_(5e_Campaign_Setting)`

Do not require MediaWiki APIs or site-specific adapters for the first release.

### Pending Presentation

Replace the simple list with a table or richer list model. Suggested columns:

| Column | Purpose |
| --- | --- |
| Include | Allows individual page inclusion/exclusion without deleting metadata |
| Source | Canonical page URL |
| Output | Planned flattened Markdown or HTML filename |
| Wiki import | Identifies the discovery run |
| Status | Discovered, excluded, failed, or converted |

Keep the current remove and clear actions. For wiki pages, an **Include**
checkbox is preferable to destructive removal because link rewriting must know
which discovered destinations are excluded. The final conversion set is all
included pending items.

## Architecture

Split wiki functionality into focused modules rather than adding it to the
already large `main.py`.

### `wiki_model.py`

Add serializable models such as:

```python
@dataclass(slots=True)
class WikiPage:
    id: str
    import_id: str
    original_url: str
    canonical_url: str
    fetched_at: str
    relative_path: str
    output_filename: str
    outgoing_urls: list[str]
    snapshot_key: str
    content_hash: str
    included: bool = True
    discovery_status: str = "discovered"
    status_message: str = ""

@dataclass(slots=True)
class WikiImport:
    id: str
    start_url: str
    root_url: str
    scope: str
    respect_robots_txt: bool
    download_assets: bool
    pages: list[WikiPage]
    discovered_at: str
```

Use stable UUIDs for import/page identity. Do not use mutable URLs or filenames
as identity.

### `wiki_urls.py`

Provide pure, independently tested helpers for:

- URL canonicalization
- relative-link resolution with `urljoin`
- fragment removal for fetch identity
- origin, current-directory, and descendant-directory checks
- query-parameter policy
- wiki-root and sub-wiki-root derivation
- relative path calculation
- deterministic flattened filename generation for Markdown and HTML
- collision resolution

### `wiki_discovery.py`

Provide the crawler and a Qt worker wrapper:

- `WikiCrawler` contains network-independent crawl orchestration that can be
  unit tested with an injected fetcher.
- `WikiDiscoveryWorker(QThread)` invokes the crawler and emits progress,
  discovered-page batches, warnings, completion, and cancellation.
- Use a queue-based breadth-first traversal so pages nearest the starting page
  appear first.
- Maintain `queued`, `visited`, and canonical URL maps to prevent loops.
- Do not impose a page-count limit. Continue until the queue is exhausted or the
  user cancels.
- Parse HTML with an explicitly declared HTML parser dependency. Do not rely on
  a transitive dependency.
- Record normalized outgoing wiki-page links for every fetched page, including
  links to already visited pages.
- Write fetched HTML and optional downloaded assets to the wiki import cache as
  discovery proceeds.
- Record the original requested URL and UTC fetch timestamp for every page.
- Preserve the supplied start page as the first pending page.

### `wiki_conversion.py`

Provide wiki-specific preparation and link mapping:

- Build the final `canonical URL -> output filename` map from included pages
  before any page is converted, using the selected Markdown or HTML extension.
- Read each included page from its discovery snapshot rather than re-fetching
  it. If a snapshot is missing or fails its content-hash check, report that page
  as unavailable and offer rediscovery instead of silently using newer content.
- Rewrite eligible internal links in the snapshot HTML to mapped output
  filenames before passing the HTML to Docling.
- After Markdown export, run a Markdown-aware link-rewrite/verification pass to
  catch absolute and relative forms that Docling retained. Avoid a broad regex
  over Markdown because it can corrupt images, code spans, reference
  definitions, and autolinks.
- After HTML export, use an HTML parser to rewrite and verify `href` and
  downloaded-asset references.
- Add page provenance at the top of every output using the original requested URL
  and the snapshot fetch timestamp:
  - Markdown uses YAML frontmatter.
  - HTML uses a leading HTML comment before the doctype or document content.
- Leave fragments on rewritten links, for example
  `page.html#setup` becomes `page.md#setup` for Markdown or
  `page.html#setup` for HTML.
- Leave links to excluded, failed, out-of-scope, non-HTML, and external
  destinations as absolute web URLs.
- When asset downloading was selected, copy cached assets into an `assets`
  directory beneath the target directory and rewrite references to relative
  `assets/...` paths. Otherwise preserve their absolute web URLs.

The wiki conversion path should reuse `_export_document`, severity handling,
result payloads, and converted-history integration from `conversion_logic.py`.
It should not force unrelated local-file conversions through crawler-specific
logic.

### `main.py`

Keep top-level UI orchestration here initially:

- launch and close the Add Wiki dialog
- start/cancel the discovery worker
- merge discovered pages into workspace state
- render pending wiki pages
- construct normal and wiki conversion jobs
- disable conflicting controls during discovery/conversion
- show partial-discovery warnings and limits
- ask whether linked assets should be downloaded
- show inferred-root confirmation when it differs from the supplied page URL
- display the complete conflict list and require overwrite-all confirmation or
  cancellation

If the pending table and dialog make `main.py` materially larger, extract
`WikiImportDialog` and the pending table model into `wiki_ui.py`.

## URL and Crawl Rules

### Canonicalization

Canonical URLs should:

- accept only `http` and `https`
- lowercase scheme and hostname
- remove default ports
- remove fragments for page identity while retaining fragments on individual
  outgoing links
- normalize dot segments and repeated slashes in the path
- preserve a meaningful trailing slash
- percent-decode only unreserved characters
- reject embedded credentials
- use the final response URL after redirects as the canonical page identity

Use this initial query policy:

- drop known tracking parameters such as `utm_*`, `fbclid`, and `gclid`
- preserve other query parameters because they may identify real wiki pages
- sort retained parameters for stable identity
- allow the user to exclude parameter patterns in a later release

Honor an HTML `<link rel="canonical">` only when it remains inside the selected
scope. Record aliases so links using either the requested or canonical URL map
to the same output.

### Link Eligibility

Follow only links that:

- resolve to HTTP/HTTPS
- remain within the selected origin and root/sub-wiki path boundary
- are not marked `rel="nofollow"` when the configured policy honors it
- are not obvious actions such as edit, history, login, logout, upload, search,
  print, or raw views
- do not have a known non-HTML extension
- return an HTML-compatible content type

Ignore:

- `mailto:`, `tel:`, `javascript:`, `data:`, and other schemes
- fragments as separate pages
- images, stylesheets, scripts, archives, media, PDFs, and other attachments
- form actions

Record ignored and failed links as crawl diagnostics, not pending pages.

### Redirects and Boundaries

- Limit redirect hops.
- Reject a redirect whose final URL leaves the allowed origin/path scope.
- Deduplicate aliases that redirect to the same final URL.
- Show a warning if the starting page itself redirects outside the user-selected
  root instead of silently widening the crawl.

### Network Safety and Politeness

- Perform all network work off the GUI thread.
- Set a descriptive user agent.
- Apply connect/read timeouts and a maximum response size.
- Do not cap the number of discovered pages. Show a live count and let the user
  cancel; rely on canonical `visited` tracking to terminate cyclic graphs.
- Use bounded concurrency or initially crawl serially; do not create an
  unbounded request pool.
- Add a small per-host delay and retry only transient failures with bounded
  backoff.
- Respect `robots.txt` by default and surface blocked pages. Let the user
  explicitly disable this behavior for a wiki they are authorized to crawl.
- Support only public pages that do not require authentication. Do not send
  existing browser cookies or credentials and do not add login flows in the
  first release.
- Block localhost, loopback, link-local, and private-network destinations by
  default to reduce SSRF-like behavior from redirects or hostile links.
- Make cancellation cooperative between requests and stop cleanly when the app
  closes.
- Return partial discovery results with per-page errors rather than discarding
  the entire crawl after one failure.

## Snapshot and Asset Cache

- Store discovery artifacts under
  `~/.docling-converter/cache/wiki/<import-id>/`, resolved through a new helper
  in `workspace_paths.py`.
- Write a cache manifest atomically with canonical URLs, relative snapshot
  paths, content hashes, original requested URLs, UTC fetch timestamps, response
  metadata, and downloaded asset mappings.
- Store only cache keys and hashes in workspace JSON, not HTML bodies.
- Use deterministic hashed cache filenames so hostile URL paths cannot escape
  the cache directory.
- Treat the cache as required input to conversion. If it is missing or corrupt,
  keep affected pages Pending and offer to rediscover the import.
- Add an explicit **Clear unused wiki cache** action. Do not delete snapshots
  merely because a page is excluded; saved workspaces may still reference them.

When **Download linked assets** is enabled:

- snapshot embedded images and directly linked non-HTML attachments discovered
  from included pages
- skip scripts, tracking pixels, and stylesheets in the first release
- enforce per-asset and total-import byte limits even though page discovery
  itself has no page-count limit
- deduplicate assets by canonical URL and content hash
- assign deterministic Windows-safe names, adding a short URL hash on collision
- copy them to `<target>/assets/` during conversion and rewrite page references

When disabled, normalize asset references to absolute web URLs.

## Output Provenance

Every generated wiki page records where and when its cached source was fetched.
Use the first requested URL that produced that page, before redirect and
canonical-link resolution, as `original_url`. Keep canonical and alias URLs in
the workspace/cache graph, but do not substitute them for the requested URL in
output provenance.

Store `fetched_at` as an RFC 3339 UTC timestamp with a `Z` suffix, generated when
the response body finishes downloading. Reusing a cached snapshot must preserve
its original fetch timestamp; conversion time is not a fetch time.

Markdown output starts with:

```yaml
---
original_url: "https://example.com/wiki/page"
fetched_at: "2026-07-12T17:58:42Z"
---
```

HTML output starts with a comment before the doctype or other content:

```html
<!--
original_url: https://example.com/wiki/page
fetched_at: 2026-07-12T17:58:42Z
-->
```

Serialize values safely rather than interpolating unescaped URL text. Emit
exactly one application provenance block per output. The block must remain first
after temporary-file finalization and link rewriting.

## Output Filename Rules

Generate all filenames before conversion so link rewriting is stable.

1. Determine the page path relative to the selected wiki root.
2. URL-decode safe path characters.
3. Remove a terminal `.html` or `.htm`.
4. Convert an empty path or trailing-slash page to an `index` component.
5. Join path components with `-`.
6. Sanitize characters invalid on Windows and trim trailing spaces/dots.
7. Prevent reserved Windows device names.
8. Add `.md` for Markdown export or `.html` for HTML export.

Examples:

| Relative source | Markdown | HTML |
| --- | --- | --- |
| `a/subject/page.html` | `a-subject-page.md` | `a-subject-page.html` |
| `a/subject/` | `a-subject-index.md` | `a-subject-index.html` |
| `index.html` | `index.md` | `index.html` |

Filename collisions are possible through case folding, punctuation
sanitization, query strings, `index` handling, or already flattened paths.
Resolve them deterministically by:

1. sorting canonical URLs
2. assigning the preferred name to the first URL
3. appending a short stable hash of the canonical URL to later collisions

Do not use `_resolve_unique_path` for wiki filename planning: numeric suffixes
depend on existing files and conversion order, which would make rewritten links
unstable. Before conversion, collect every existing target conflict, display the
full list, and ask the user to **Confirm overwrite** or **Cancel**. Confirmation
applies to the complete displayed conflict set; do not partially overwrite
without approval.

## Workspace Model and Persistence

Evolve `WorkspaceData` without breaking existing workspaces:

- keep normal local/URL sources supported
- replace or supplement `pending_sources: list[str]` with typed pending items
- add `wiki_imports: list[WikiImport]`
- preserve enough graph data to reopen a workspace, edit included pages, and
  convert without rediscovery
- include wiki identity and source URL in converted history

Recommended typed queue model:

```python
@dataclass(slots=True)
class PendingItem:
    id: str
    kind: str  # file, url, wiki_page
    source: str
    included: bool = True
    wiki_import_id: str | None = None
    wiki_page_id: str | None = None
```

Increment `WORKSPACE_FILE_VERSION` to `2`. `load_workspace` should migrate
version `1` `pending_sources` into typed pending items, not reject existing user
files. Continue writing only the newest version.

Do not store fetched HTML bodies in workspace JSON. Persist each page's cache key
and content hash so conversion uses the exact discovery snapshot. Persist
excluded pages in the wiki graph with `included=False`; they remain available
for later re-inclusion and their links remain web URLs while excluded.

## Conversion Lifecycle

1. User completes wiki discovery and edits inclusion in **Pending**.
2. Validate the target directory and require Markdown or HTML output for wiki
   jobs in the first release. JSON and DocTags remain single-document-only.
3. Freeze a conversion manifest containing the selected pages and final filename
   map.
4. Validate snapshot hashes and asset availability.
5. Build and display the complete target conflict list. Continue only if the
   user confirms overwriting the listed files; otherwise cancel without writes.
6. Read and prepare each cached page, convert it with Docling, verify/rewrite
   links, add provenance from the cache manifest, and write its predetermined
   output path.
7. Emit one result row per page.
8. Remove only successful pages from Pending. Keep failed pages for retry.
9. Add successful pages to Converted history.
10. Persist enough status that saving the workspace after partial failure does
   not lose the graph or inclusion choices.

If a destination page fails conversion, links from successful pages should
remain absolute web URLs. Because the final success set is not known until the
batch ends, either:

- convert to temporary files and perform a final link rewrite after all results
  are known; or
- initially rewrite against the selected set, then run a final repair pass that
  restores web URLs for failed destinations.

The temporary-output approach is safer and provides batch-like behavior:
prepare all outputs in a temporary directory, finalize links from the successful
set, then move successful files into the target directory.

## Dependency Changes

Add direct dependencies only when implementation begins:

- an HTML parser, likely `beautifulsoup4` with `lxml`, for tolerant link
  extraction and HTML rewriting
- a Markdown parser/tokenizer that can safely rewrite destinations while
  preserving source formatting, or a proven Markdown link rewriting library

Use `uv add` so `pyproject.toml` and `uv.lock` stay synchronized. Evaluate
whether the standard library HTTP stack is sufficient; otherwise add `httpx`
for explicit timeout, redirect, streaming-size, and cancellation handling.

## Detailed Implementation Phases

### Phase 1: URL and Filename Foundation

- Add `wiki_model.py` and `wiki_urls.py`.
- Implement canonicalization, scope checks, relative paths, flattened names, and
  deterministic collision handling.
- Add original-URL and UTC fetch-timestamp fields to page/cache models.
- Unit test Windows-safe naming and adversarial URL cases.

### Phase 2: Discovery Engine

- Add parser/fetcher abstractions and `WikiCrawler`.
- Implement breadth-first discovery, outgoing-link graph recording, redirect
  handling, snapshots, robots policy and override, cancellation, and partial
  errors.
- Implement unlimited page traversal with canonical loop detection and bounded
  request/response sizes.
- Add optional asset discovery and caching.
- Test with an in-process/fake HTTP graph; unit tests must not depend on public
  internet access.

### Phase 3: Workspace Migration

- Introduce typed pending items and wiki imports.
- Add version `1` to version `2` migration.
- Update save/load, queue synchronization, and converted-history models.
- Verify existing saved workspace fixtures still load.

### Phase 4: Wiki UI and Review

- Add the **Add wiki...** dialog and scope controls.
- Add background discovery progress/cancellation.
- Upgrade Pending presentation to support source, output name, import grouping,
  status, and inclusion.
- Preserve all existing file, directory, URL, drag/drop, remove, and clear
  behavior.

### Phase 5: Wiki Conversion and Link Rewriting

- Freeze the batch manifest and filename map.
- Read/preprocess cached HTML and integrate Markdown and HTML Docling conversion.
- Present conflicts and require overwrite-all confirmation or cancellation.
- Write to temporary outputs, finalize page and asset links using successful
  pages, and move results into the target directory.
- Add YAML provenance frontmatter to Markdown and leading provenance comments to
  HTML using snapshot metadata.
- Surface page-level errors and preserve failed pending items.

### Phase 6: Hardening and Documentation

- Add request/response and asset-size safety limits, cache cleanup, diagnostics,
  and cancellation on close.
- Update `README.md`, `IMPLEMENTATION.md`, `PROJECT_PLAN.md`,
  `PENDING_TASKS.md`, `COMPLETED_TASKS.md`, and `TEST.md` to match implemented
  behavior.
- Perform manual smoke tests against `https://foundryvtt.com/api/v13/` and
  `https://www.dandwiki.com/wiki/Hyrule_(5e_Campaign_Setting)`.

## Test Plan

### URL and Scope Unit Tests

- relative, root-relative, protocol-relative, absolute, query, and fragment links
- fragments do not create duplicate pages
- same host but outside root is excluded
- deceptive hostnames such as `wiki.example.com.evil.test` are excluded
- default ports and hostname case canonicalize correctly
- redirect and canonical aliases deduplicate
- sub-wiki includes the starting page when supplied with a fragment
- sub-wiki recursively includes linked child-directory pages
- sub-wiki includes directly linked same-directory pages only one level deep
- same-directory pages do not expand to additional same-directory pages
- non-HTTP schemes and non-HTML extensions are ignored

### Filename Unit Tests

- required `a/subject/page.html -> a-subject-page.md` example
- roots, trailing slashes, index pages, percent encoding, Unicode, and queries
- Windows invalid characters and reserved names
- case-insensitive and sanitization collisions
- deterministic hash suffixes independent of crawl order

### Crawler Unit Tests

- cycles, self-links, duplicate links, and multiple paths to one page
- breadth-first ordering
- whole-wiki versus sub-wiki boundaries
- unlimited page traversal terminates for cyclic graphs
- response-size and asset byte limits
- timeout, 404, 429, 500, malformed HTML, wrong content type, and redirect errors
- robots exclusion and explicit user override
- cancellation and partial-result return
- every page records its normalized outgoing internal links
- page and optional asset snapshots are cached with verified content hashes

### Workspace and UI Tests

- version `1` migration and version `2` round trip
- wiki graph, inclusion, planned filenames, and diagnostics persist
- Add Wiki dialog validation
- discovery runs off-thread and controls enter/leave busy state
- inferred roots that differ from the supplied URL require confirmation
- discovered pages appear in Pending
- individual inclusion/removal updates workspace state while retaining excluded
  graph nodes
- asset-download and robots-policy choices persist
- missing cache entries keep pages pending and offer rediscovery
- original requested URLs and fetch timestamps survive workspace round trips
- existing file/directory/single-URL flows remain unchanged
- closing waits for or cancels both discovery and conversion workers

### Conversion and Link Tests

- all included pages receive predetermined flattened names for Markdown and HTML
- relative, absolute, root-relative, query-bearing, and fragment links rewrite
  correctly in Markdown and HTML
- excluded, failed, external, and attachment links remain absolute web URLs
- images and code containing URL-like text are not corrupted
- opted-in assets are copied to `assets/`, deduplicated, and rewritten
- opted-out assets remain absolute web URLs
- page failures remain pending while successes enter Converted
- all target-file conflicts are listed before writes
- cancelling the conflict prompt performs no target writes
- confirming the conflict prompt overwrites the complete displayed set
- custom single-output filename does not override wiki batch filenames
- wiki conversion accepts Markdown and HTML and rejects JSON and DocTags
- Markdown begins with exactly one valid YAML frontmatter block containing
  `original_url` and the RFC 3339 UTC `fetched_at` value
- HTML begins with exactly one comment containing the same provenance fields
- redirected pages report the original requested URL, not the final canonical URL
- cached conversion preserves the snapshot fetch timestamp rather than using the
  conversion time
- provenance values containing YAML- or HTML-sensitive characters are serialized
  safely
- provenance remains first after link rewriting and output finalization

### Manual Tests

- start from a non-root page and discover a whole wiki
- start from the same page and confirm sub-wiki results are narrower
- review, exclude, re-include, remove, save, close, reload, and convert
- cancel a large discovery and retain usable partial results
- verify generated Markdown and HTML batches use one directory and links open the
  corresponding local output file
- verify conversion works from cached snapshots with the network disconnected
- test asset download enabled and disabled
- test the robots override on a site the tester is authorized to crawl
- inspect behavior on redirects, canonical links, Unicode URLs, and pages with
  navigation-heavy templates

Run the existing suite throughout implementation:

```bash
uv run python -m pytest -q
```

## Acceptance Criteria

- A user can start wiki discovery from any valid page URL.
- Whole-wiki root inference is visibly editable and requires confirmation when
  it differs from the supplied page URL.
- Sub-wiki mode includes the starting page, recursively follows linked
  child-directory pages, and follows same-directory links one level.
- Discovery does not freeze the GUI and can be cancelled.
- Discovery has no page-count limit, terminates loops through canonical URL
  tracking, and snapshots fetched content in the application cache.
- Every discovered page and its outgoing internal wiki links are recorded in
  workspace state.
- Discovered pages are added to Pending and can be individually included,
  excluded, or removed while remaining represented in the graph.
- Saving and reopening a workspace preserves the wiki graph and review choices.
- Existing version `1` workspaces migrate without data loss.
- Included pages convert to Markdown or HTML files in one target directory using
  stable flattened relative-path names.
- Every Markdown output begins with YAML frontmatter containing its original URL
  and UTC fetch timestamp.
- Every HTML output begins with a comment containing its original URL and UTC
  fetch timestamp.
- Links between successfully converted included pages target the correct local
  output filenames; all other links remain usable web URLs.
- The user chooses whether linked assets remain remote or are downloaded to the
  target `assets` directory.
- Existing target conflicts are fully listed and no overwrite occurs without
  explicit confirmation.
- Crawl loops, redirects, failures, collisions, target-file conflicts, and
  request/response limits produce explicit user-visible outcomes.
- Existing local file, directory, single URL, PDF chunking, and non-wiki export
  behavior continue to pass their tests.

## Questions

All current questions are resolved below. Revisit the initial sub-wiki traversal
rule after testing it against representative path-based and same-directory wiki
structures.

### 1. Sub-wiki Boundary

**Question:** How should "sub-wiki" define adjacent or underneath pages? Should
same-level sibling pages, sidebar-linked pages, MediaWiki categories, or another
hierarchy count?

**Answer:** The sub-wiki includes the current page even when the supplied URL
uses a `#fragment` to focus on a heading. It recursively includes linked pages
below the current page in the directory structure and includes one level of
pages linked from the current page in the current directory. This rule may
change later.

**Implications:**

- Fragments are retained for navigation but removed from page identity.
- Child-directory links are traversed recursively.
- Same-directory links from the starting page are included for one hop.
- Same-directory pages do not recursively expand to more same-directory pages.
- Breadcrumbs, incoming links, sidebar position, and wiki categories do not
  independently establish membership in the first release.
- Tests must distinguish starting-page, child-directory, and one-hop
  same-directory traversal.

### 2. Whole-wiki Root Detection

**Question:** How should the whole-wiki root be detected? Should it be inferred,
confirmed, editable, or always use the entire origin?

**Answer:** Infer the root. If the inferred root differs from the provided page
URL, show both and require user confirmation before discovery.

**Implications:**

- Root inference must be deterministic and separately tested.
- A trailing-slash URL initially remains its own root; a page-like URL initially
  infers its containing directory.
- The confirmation dialog must allow editing the inferred root.
- Discovery must not begin until a differing root is confirmed.
- Root confirmation never permits silently changing the origin.

### 3. Supported Wiki Types

**Question:** Should the first release target generic wiki-like HTML sites,
MediaWiki specifically, or both?

**Answer:** Target generic wiki-like sites. Representative examples are
`https://foundryvtt.com/api/v13/` and
`https://www.dandwiki.com/wiki/Hyrule_(5e_Campaign_Setting)`.

**Implications:**

- The crawler must use standards-based HTML links and URL structure rather than
  requiring a wiki API.
- MediaWiki-specific categories, namespaces, or APIs are not required initially.
- Automated tests use local/fake HTML graphs; the two example sites are manual
  acceptance targets.
- Site-specific adapters can be added later without replacing the generic
  crawler.

### 4. Discovery Page Limit

**Question:** What default and maximum page-count limits should apply?

**Answer:** Do not impose a page-count limit. Continue until all eligible links
are checked, assuming loops are detected.

**Implications:**

- Canonical URL identity and `queued`/`visited` sets are correctness-critical.
- The UI must show live discovery counts and provide cancellation.
- Discovery continues until the queue is exhausted or the user cancels.
- Request timeouts, response-size limits, bounded concurrency, and asset-byte
  limits still apply; unlimited pages does not mean unlimited individual
  responses.
- Tests must prove termination for cycles, aliases, fragments, and redirects.

### 5. `robots.txt`

**Question:** Must `robots.txt` always be respected, or may the user override it
for a wiki they are authorized to crawl?

**Answer:** Respect `robots.txt` by default, but allow the user to override it.

**Implications:**

- Add a persisted **Respect robots.txt** option enabled by default.
- Blocked URLs must be reported as diagnostics when the option is enabled.
- Disabling the option must be an explicit user action with clear wording about
  authorization.
- Both enabled and overridden behavior require automated coverage.

### 6. Authentication and Private Wikis

**Question:** Must private or intranet wikis be supported, and are cookies,
HTTP basic authentication, or other credentials required?

**Answer:** Start with wikis that do not require authentication.

**Implications:**

- Do not add login flows, credential storage, browser-cookie reuse, or
  authenticated request configuration in the first release.
- Authentication failures remain explicit page-level discovery errors.
- Localhost, loopback, link-local, and private-network targets remain blocked by
  default.
- Authenticated and private-wiki support can be designed separately later.

### 7. Discovery Snapshot and Cache

**Question:** Should discovery save an HTML snapshot for later conversion, or
should conversion re-fetch each page?

**Answer:** Discovery should snapshot and cache fetched pages.

**Implications:**

- Cache HTML under `~/.docling-converter/cache/wiki/<import-id>/`.
- Persist cache keys and content hashes in workspace state, not HTML bodies.
- Persist each page's original requested URL and UTC fetch timestamp so every
  generated output can carry stable provenance.
- Conversion uses the exact cached discovery content and can work offline.
- Missing or corrupt cache entries keep pages Pending and prompt rediscovery
  rather than silently fetching changed content.
- Cache manifests require atomic writes, safe filenames, cleanup controls, and
  tests for integrity and missing data.

### 8. Existing Target-file Conflicts

**Question:** How should existing target files be handled for a wiki batch:
overwrite, skip, abort, or rename?

**Answer:** Display the complete conflict list and ask the user to confirm or
cancel the overwrite.

**Implications:**

- Compute all final filenames before conversion.
- Detect and display every conflict before writing any target file.
- Confirmation authorizes overwriting the complete displayed set.
- Cancellation performs no target writes.
- Do not silently skip, auto-rename, or partially overwrite files.

### 9. Initial Export Formats

**Question:** Should wiki import be Markdown-only initially, or should other
export formats be supported?

**Answer:** Support Markdown and HTML in the first pass. Add JSON and DocTags
later.

**Implications:**

- Filename planning uses `.md` or `.html` according to the selected format.
- Internal links must be rewritten and verified for both output formats.
- Use Markdown-aware rewriting for Markdown and parser-based rewriting for HTML.
- Wiki conversion must reject JSON and DocTags with a clear validation message.
- Existing single-document JSON and DocTags conversion remains unchanged.

### 10. Images and Attachments

**Question:** Should linked images and attachments be downloaded?

**Answer:** Ask the user whether to download assets. When enabled, save them to
an `assets` directory.

**Implications:**

- Add a per-import **Download linked assets** choice, disabled by default.
- When enabled, cache eligible images and linked non-HTML attachments during
  discovery, copy them to `<target>/assets/`, and rewrite references.
- When disabled, preserve normalized absolute web URLs.
- Asset downloads require deterministic collision-safe names, deduplication,
  response and total-byte limits, and partial-failure diagnostics.
- Scripts, stylesheets, and tracking pixels remain excluded initially.

### 11. Removed Pending Pages

**Question:** When a page is removed from Pending, should it remain represented
as an excluded page in the wiki graph?

**Answer:** Yes.

**Implications:**

- Removal changes inclusion state instead of deleting graph metadata.
- Excluded pages survive workspace save/load and can be re-included.
- Links to excluded pages remain absolute web URLs.
- Removing one page does not recursively remove or exclude descendants.
- The Pending UI should distinguish exclusion from permanent graph deletion.

### 12. Query-string Identity

**Question:** Should query strings identify distinct pages?

**Answer:** Yes.

**Implications:**

- Remove known tracking parameters such as `utm_*`, `fbclid`, and `gclid`.
- Preserve and sort all other query parameters for canonical identity.
- Different retained query values can produce distinct pending pages.
- Filename collision handling must add a stable URL hash when query-distinct
  pages flatten to the same preferred filename.
- Action-like queries such as edit, history, login, logout, print, search, and
  raw views remain excluded by link-eligibility rules.
