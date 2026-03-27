---
phase: 02-collection-engine
plan: 02
subsystem: collection
tags: [feedparser, beautifulsoup4, lxml, httpx, rss, html-parsing, async]

# Dependency graph
requires:
  - phase: 02-collection-engine/01
    provides: "source_detector.py (detect_source_type), keyword_filter.py (filter_articles, matches_keywords)"
  - phase: 01-foundation
    provides: "database.py (get_db, init_db), config.py (paths), logger.py (get_logger)"
provides:
  - "RSS feed parser (parse_rss) using feedparser"
  - "HTML article link extractor (parse_html) using BeautifulSoup4+lxml"
  - "Collection orchestrator (collect_all_sources, collect_source) with dedup and error isolation"
affects: [03-summarization-pipeline, 04-bot-interface]

# Tech tracking
tech-stack:
  added: [feedparser, beautifulsoup4, lxml]
  patterns: [async-httpx-fetch-then-parse, insert-or-ignore-dedup, per-source-error-isolation]

key-files:
  created:
    - src/collector/rss_collector.py
    - src/collector/html_collector.py
    - src/collector/collector.py
  modified: []

key-decisions:
  - "Used cursor.rowcount instead of db.total_changes for accurate new article counting"
  - "Browser-like User-Agent for HTML collector to avoid blocks from Korean news sites"
  - "Auto-detected source type persisted to DB so detection runs only once per source"

patterns-established:
  - "Fetch-then-parse: httpx fetches content, then library-specific parser processes it"
  - "Per-source error isolation: each source wrapped in try/except, failures logged and skipped"
  - "Keyword loading from DB each cycle: supports dynamic keyword changes via bot"

requirements-completed: [COL-01, COL-02, COL-03, COL-04, COL-07, COL-08]

# Metrics
duration: 3min
completed: 2026-03-27
---

# Phase 02 Plan 02: Collection Engine Summary

**RSS and HTML parsers with collection orchestrator providing fetch-parse-filter-store pipeline with URL deduplication and per-source error isolation**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-27T00:22:03Z
- **Completed:** 2026-03-27T00:25:06Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- RSS collector parses feeds via feedparser, extracting title/url/published_at from entries
- HTML collector extracts article links from pages using generic URL pattern matching with BeautifulSoup4+lxml
- Collection orchestrator processes all enabled sources with type detection, keyword filtering, dedup, and error isolation

## Task Commits

Each task was committed atomically:

1. **Task 1: Create RSS collector using feedparser** - `092113c` (feat)
2. **Task 2: Create HTML collector using BeautifulSoup4** - `21accf7` (feat)
3. **Task 3: Create collection orchestrator with deduplication and error handling** - `f1e6e71` (feat)

## Files Created/Modified
- `src/collector/rss_collector.py` - Async RSS/Atom feed parser using httpx + feedparser
- `src/collector/html_collector.py` - Generic HTML article link extractor using httpx + BeautifulSoup4 + lxml
- `src/collector/collector.py` - Collection orchestrator: source iteration, type detection, parsing, filtering, dedup storage

## Decisions Made
- Used `cursor.rowcount` instead of `db.total_changes` for accurate insert counting (total_changes is cumulative and unreliable per-statement)
- Browser-like User-Agent for HTML collector to avoid being blocked by Korean news sites
- Auto-detected source type is persisted to DB to avoid repeated network requests for type detection

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed new article counting using cursor.rowcount**
- **Found during:** Task 3 (Collection orchestrator)
- **Issue:** Plan used `db.total_changes` which is a cumulative counter, not per-statement -- would produce incorrect new_count
- **Fix:** Used `cursor.rowcount` from the INSERT OR IGNORE result instead
- **Files modified:** src/collector/collector.py
- **Verification:** Code review confirms cursor.rowcount is correct for aiosqlite INSERT OR IGNORE
- **Committed in:** f1e6e71 (Task 3 commit)

**2. [Rule 3 - Blocking] Installed missing feedparser, beautifulsoup4, lxml packages**
- **Found during:** Task 1 (RSS collector verification)
- **Issue:** feedparser, beautifulsoup4, lxml not installed in environment
- **Fix:** Ran `python -m pip install feedparser beautifulsoup4 lxml`
- **Files modified:** None (runtime dependency)
- **Verification:** Import succeeds, verification scripts pass

---

**Total deviations:** 2 auto-fixed (1 bug fix, 1 blocking)
**Impact on plan:** Both fixes necessary for correctness and execution. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all functions are fully implemented with real logic.

## Next Phase Readiness
- Collection engine complete: RSS parser, HTML parser, and orchestrator ready
- Plan 02-03 (collection scheduling/integration) can proceed
- Phase 03 (summarization pipeline) can access collected articles via the articles table

## Self-Check: PASSED

- [x] src/collector/rss_collector.py exists
- [x] src/collector/html_collector.py exists
- [x] src/collector/collector.py exists
- [x] Commit 092113c found
- [x] Commit 21accf7 found
- [x] Commit f1e6e71 found

---
*Phase: 02-collection-engine*
*Completed: 2026-03-27*
