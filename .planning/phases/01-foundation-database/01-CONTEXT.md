# Phase 1: Foundation & Database - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the async runtime, SQLite database with all 6 tables, configuration loading, logging, and project scaffolding. Everything subsequent phases build on.

</domain>

<decisions>
## Implementation Decisions

### Stack Deviations from SOP (Research-backed)
- **D-01:** Use `httpx` instead of `requests` — async HTTP client, already a transitive dependency of anthropic SDK and python-telegram-bot
- **D-02:** Use `aiosqlite` instead of raw `sqlite3` — prevents blocking the asyncio event loop during DB operations
- **D-03:** Use python-telegram-bot's built-in `JobQueue` instead of separate APScheduler — avoids event loop conflicts, JobQueue wraps APScheduler internally

### Project Structure
- **D-04:** Code lives at repo root (not in a news-briefing/ subdirectory) — SOP structure directly: `src/`, `data/`, `briefings/`, `deploy/`, `logs/`

### Claude's Discretion
- Initial source data: 13 sources hardcoded in code or separate config — Claude decides best approach
- Logging: format, levels, rotation — Claude decides based on best practices
- DB migration strategy for schema changes — Claude decides

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Specification
- `SOP.md` — Complete system specification v2.1 with DB schema, bot commands, project structure, deployment details
- `.planning/PROJECT.md` — Project context, core value, constraints
- `.planning/REQUIREMENTS.md` — 46 v1 requirements with REQ-IDs (Phase 1: INF-01~06, DEP-05)

### Research
- `.planning/research/STACK.md` — Technology recommendations (httpx, aiosqlite, APScheduler v3 pin, lxml)
- `.planning/research/ARCHITECTURE.md` — Component boundaries and data flow
- `.planning/research/PITFALLS.md` — SQLite WAL mode, event loop conflicts, encoding issues

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project

### Established Patterns
- None — patterns will be established in this phase

### Integration Points
- This phase creates the foundation all other phases connect to: DB layer, async runtime, bot Application instance, JobQueue

</code_context>

<specifics>
## Specific Ideas

- SOP Section 3 defines exact SQL CREATE TABLE statements — use as-is
- SOP Section 15 defines 13 initial sources with names and URLs
- SOP Section 8 defines the main.py async structure pattern
- requirements.txt should reflect stack changes: httpx instead of requests, add aiosqlite, keep apscheduler (used internally by JobQueue)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation-database*
*Context gathered: 2026-03-26*
