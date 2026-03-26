# Project Research Summary

**Project:** Automated News Briefing System (IT/semiconductor/AI niche)
**Domain:** News aggregation with AI summarization and Telegram bot delivery
**Researched:** 2026-03-26
**Confidence:** MEDIUM-HIGH

## Executive Summary

This is a team-shared news briefing system that aggregates articles from 13 Korean and English IT/semiconductor sources, filters by keywords, generates one-line Korean summaries using Claude AI, and delivers scheduled briefings via Telegram. The recommended approach is a single-server Python application built on SQLite + python-telegram-bot + APScheduler + Anthropic SDK with an async-first architecture. All components run in a single process sharing one asyncio event loop.

The key architectural insight from research is that python-telegram-bot v20+ is fully async and owns the event loop, which dictates the entire concurrency model. Using `httpx` (already a dependency of the Anthropic SDK) for async HTTP, `AsyncIOScheduler` for job scheduling, and `aiosqlite` for database access creates a clean single-event-loop architecture. The stack is well-chosen: every technology selection is defensible for a 2-5 person team running on a single GCP instance.

The primary risks are operational fragility (HTML parsers breaking when sites redesign, API costs spiraling from naive summarization, event loop conflicts between bot and scheduler) and bilingual complexity (Korean/English mixed content with encoding issues). Mitigation is straightforward: batch Claude API calls, enable SQLite WAL mode from day one, use python-telegram-bot's built-in `JobQueue` instead of separate APScheduler to avoid event loop conflicts, and implement zero-article monitoring for broken parsers. The research has high confidence in table-stakes features and architecture patterns (well-established domain), medium confidence on specific version numbers (based on training data through early 2025, not live verification).

## Key Findings

### Recommended Stack

The SOP-specified stack is appropriate with two critical adjustments: prefer `httpx` over `requests` (httpx is already a transitive dependency of the Anthropic SDK and supports async natively), and pin APScheduler to v3.x (v4 is a breaking rewrite). The async-first pattern is essential: python-telegram-bot v20+ runs on asyncio, so all I/O must be async-compatible to avoid blocking the event loop.

**Core technologies:**
- **Python 3.11+**: Use 3.12 if available on GCP for improved f-strings and error messages
- **SQLite with WAL mode**: Zero-config, perfect for single-server low-write-volume workload. WAL mode enables concurrent reads during writes
- **python-telegram-bot >=21.0**: Mature async Telegram library with ConversationHandler for multi-step bot flows
- **httpx >=0.27.0**: Async HTTP client (already a dependency of anthropic SDK). Replaces `requests` which has no async support
- **Anthropic Python SDK >=0.40.0**: Official Claude API client with built-in retries for claude-sonnet-4-20250514
- **feedparser >=6.0.11**: Standard RSS/Atom parser, handles malformed feeds gracefully
- **beautifulsoup4 >=4.12.0 + lxml >=5.0.0**: Industry standard for HTML scraping with fast lxml backend
- **APScheduler >=3.10.0, <4.0.0**: Battle-tested cron-like scheduler. AsyncIOScheduler integrates with asyncio event loop. Pin to v3.x — v4 is alpha/beta quality

**Critical version note:** APScheduler v4 is a complete rewrite with incompatible API. Avoid it. Use v3.10.x.

### Expected Features

**Must have (table stakes):**
- Multi-source RSS + HTML collection with auto-detection
- Per-source keyword filtering (case-insensitive partial match)
- Claude-powered one-line summarization in Korean (regardless of source language)
- Scheduled briefing delivery (APScheduler cron jobs)
- URL-based duplicate prevention + is_briefed flag management
- Telegram bot as sole control interface (no web UI)
- Source/keyword CRUD via bot commands
- Briefing time configuration with dynamic scheduler updates
- On-demand triggers (/briefing, /collect commands)
- Multi-user delivery (iterate over registered chat_ids)
- Briefing history as .md files for archive/grep
- Error resilience per source (one broken source must not block collection cycle)

**Should have (competitive differentiators):**
- Korean + English unified output (all summaries in Korean)
- [Keyword] tag in summaries for visual scanning
- Global keywords (cross-source filtering)
- Source enable/disable without deletion
- Zero-article notification ("No new articles" instead of silence)
- Telegram message splitting for 4096-char limit
- Deletion confirmation flow for destructive actions

**Defer (v2+):**
- Briefing statistics (articles per source, keyword hit rates) — wait until system generates meaningful data
- Article content preview on demand — triggered by user need
- Briefing search/recall via bot — triggered by archive size
- Source health monitoring (auto-disable after N failures) — triggered by operational experience
- Playwright for JS-heavy sources — only if a critical source requires it

**Explicit anti-features (do NOT build):**
- Per-user customization — shared team settings are the value proposition
- Real-time push notifications — defeats the "briefing" mental model
- Full article content scraping — legal gray area, defeats one-line summaries
- Web dashboard / admin UI — Telegram IS the interface
- Sentiment analysis / categorization — adds cost without clear action
- Email / Slack delivery — multi-channel multiplies complexity
- ML relevance scoring — deterministic keywords are debuggable
- n8n / external automation — keep logic in one codebase

### Architecture Approach

The system is a single-process asyncio application with three layers: Telegram bot interface (command handlers + message sender), application core (scheduler, briefing pipeline, collectors, summarizer), and data layer (RSS/HTML parsers + SQLite). All components share a single asyncio event loop. The briefing service orchestrates a sequential pipeline: collect -> filter -> summarize -> deliver -> mark as sent -> save .md file. Parsers use a strategy pattern (base parser interface with RSS and HTML implementations) to enable per-source customization as sites break.

**Major components:**
1. **Telegram Bot Handlers** — Parse commands (/add_source, /keywords, etc.), validate, delegate to services. Thin layer over core logic.
2. **Briefing Service** — Orchestrates full pipeline from collection through delivery. The "brain" of the system.
3. **Collector Service** — Fetches from all sources, dispatches to RSS or HTML parser based on type, applies keyword filters, deduplicates.
4. **Summarizer** — Batches filtered articles into single Claude API prompt, returns structured Korean summaries.
5. **Scheduler (APScheduler AsyncIOScheduler)** — Triggers collection and briefing at configured times. Runs in same event loop as bot.
6. **Parsers (RSS + HTML)** — feedparser for RSS (handles encoding, dates, variants), httpx + BeautifulSoup4 for HTML with generic extractor + per-source overrides.
7. **Database (SQLite via aiosqlite)** — Persists sources, articles, keywords, settings, briefing history. WAL mode for concurrency.

**Recommended project structure:**
```
news_briefing/
├── bot/          # Telegram interface (handlers, commands, formatting)
├── core/         # Business logic (briefing, collector, summarizer, scheduler)
├── parsers/      # RSS, HTML, and custom per-source parsers
├── db/           # Schema, repository, migrations
├── config.py     # Environment variables, constants
└── main.py       # Entry point — wires everything together
```

**Key architectural decision:** Use python-telegram-bot's built-in `JobQueue` instead of separate APScheduler to avoid event loop ownership conflicts. The JobQueue wraps APScheduler internally and integrates cleanly with the bot's Application lifecycle.

### Critical Pitfalls

1. **Event loop conflict (bot + scheduler)** — python-telegram-bot's `run_polling()` calls `asyncio.run()` internally and owns the event loop. Running APScheduler separately causes crashes or silently dead jobs. **Avoid:** Use python-telegram-bot's built-in `JobQueue` instead of separate APScheduler, OR manually manage the event loop without `run_polling()`. This is a Phase 1 architectural decision — changing it later requires rewriting main.py.

2. **HTML parsing breaks silently when sites change layout** — Generic CSS selectors stop working after site redesigns but return 0 articles with no errors. System keeps running, users see nothing. **Avoid:** Implement zero-article monitoring from day one (track articles-found-per-source, alert via Telegram when 0 for 2+ consecutive fetches). Use RSS where possible (stable contract). Build per-source custom parsers when needed. Phase 2 critical.

3. **Claude API costs spiral from per-article summarization** — Sending each article individually means 50-100 API calls per briefing, hitting rate limits and multiplying costs. **Avoid:** Batch all filtered articles into a single prompt. Filter by keywords BEFORE calling Claude. Truncate article content to 500-1000 chars. Cache summaries keyed by URL. Phase 3 design requirement.

4. **SQLite "database is locked" under concurrent access** — Default SQLite uses file-level locking. Scheduler writes + bot reads = "database is locked" errors after 5 second timeout. **Avoid:** Enable WAL mode (`PRAGMA journal_mode=WAL`) and set busy_timeout=5000 on first connection. Never hold transactions open during I/O. Phase 1 foundation code.

5. **feedparser silently accepts broken/empty feeds** — `feedparser.parse()` never raises exceptions, returns empty or partial results for 404/timeout/invalid XML. Developers check `len(feed.entries) > 0` and assume success. **Avoid:** Check `feed.bozo` AND `feed.status`. Track last-successful-fetch per source. Validate entry structure (title + link minimum). Phase 2 collection code.

6. **Telegram message length limit truncates briefings** — 4096-char limit. 20+ article briefing exceeds this, raises `BadRequest: Message is too long`. **Avoid:** Implement `send_long_message()` helper that splits on article boundaries with [1/N] headers. Use HTML parse_mode (more predictable than MarkdownV2 escaping). Phase 4 delivery code.

7. **systemd service dies silently on unhandled async exceptions** — Unhandled exception in async task kills the task but not the process. Service shows "active" but bot is dead. **Avoid:** Set global exception handler with `loop.set_exception_handler()`. Health check via systemd WatchdogSec. RestartSec=10 to prevent throttling. Wrap all handlers in try/except. Phase 5 deployment, but error patterns must be in Phase 1 foundation.

8. **Korean/English mixed content breaks keyword matching** — Korean has no word boundaries, same concept appears in multiple languages ("반도체" vs "semiconductor"), encoding varies (UTF-8 vs EUC-KR). **Avoid:** Force UTF-8 everywhere (chardet for detection). Case-insensitive match for English, exact for Korean. Support keyword synonyms ("semiconductor|반도체" as one logical keyword). Phase 2 collection engine.

## Implications for Roadmap

Based on research, suggested phase structure with 5 phases:

### Phase 1: Foundation & Database
**Rationale:** Everything depends on data storage and the async runtime architecture. The event loop decision (JobQueue vs separate scheduler) must be correct from the start or it requires rewriting main.py later. SQLite WAL mode and error handling patterns established here propagate through all subsequent phases.

**Delivers:**
- SQLite schema (6 tables: sources, articles, source_keywords, global_keywords, settings, chat_ids)
- Database repository with async CRUD operations via aiosqlite
- WAL mode + busy_timeout configuration
- main.py with python-telegram-bot Application + JobQueue setup
- Global exception handler and logging framework
- .env configuration loading

**Addresses:**
- Pitfall #1 (event loop conflict) — use JobQueue from the start
- Pitfall #4 (SQLite locking) — WAL mode enabled in schema init
- Pitfall #7 (silent service death) — exception handling patterns established

**Avoids:** Technical debt from wrong concurrency model. All async code shares one event loop.

### Phase 2: Collection Engine
**Rationale:** Collection is the data input pipeline. RSS must work before HTML (RSS is more reliable). Keyword filtering must work before summarization (to minimize API costs by filtering locally first). Monitoring must be built from day one because HTML parsers WILL break.

**Delivers:**
- RSS parser with feedparser (validates bozo flag, HTTP status, entry structure)
- Generic HTML parser with BeautifulSoup4 + httpx AsyncClient
- Source type auto-detection (check URL patterns + Content-Type)
- Per-source keyword filtering (case-insensitive for English, exact for Korean, bilingual synonym support)
- URL-based deduplication with normalized URLs
- Concurrent source fetching with asyncio.gather() (5 concurrent limit via semaphore)
- Zero-article monitoring (alerts via Telegram when source returns 0 articles for 2+ cycles)
- Encoding detection and UTF-8 normalization for Korean sites

**Addresses:**
- Pitfall #2 (HTML parsing breaks silently) — zero-article monitoring catches it
- Pitfall #5 (feedparser silent failures) — validate bozo + status
- Pitfall #8 (Korean/English encoding) — chardet + UTF-8 normalization

**Uses:** httpx (async), feedparser, BeautifulSoup4 + lxml, aiosqlite for article storage

**Implements:** Collector Service, RSS Parser, HTML Parser from architecture

### Phase 3: Summarization & Briefing Pipeline
**Rationale:** Summarization depends on collected articles. Batching strategy must be designed before writing the first API call to avoid cost spiraling. The briefing service orchestrates the full pipeline, so it needs working collectors and a working summarizer.

**Delivers:**
- Claude API integration via Anthropic Python SDK
- Batched summarization prompt (all articles in one call, structured output)
- Article content truncation to 500-1000 chars before API call
- One-line Korean summary generation with [keyword] tags
- Briefing pipeline orchestration (collect -> filter -> summarize -> format)
- is_briefed flag management (mark articles as sent to prevent re-summarization)
- API retry logic with exponential backoff (anthropic SDK has built-in retries, enable with max_retries=3)
- Token counting and budget enforcement

**Addresses:**
- Pitfall #3 (API costs spiral) — batched prompts, filter before summarization, truncate content

**Uses:** anthropic SDK (claude-sonnet-4-20250514), aiosqlite for article reads/writes

**Implements:** Summarizer, Briefing Service from architecture

### Phase 4: Telegram Delivery & Bot Commands
**Rationale:** Delivery depends on formatted briefings. Bot commands provide the control interface. Message splitting must be built from the start because it's easier than retrofitting. All CRUD commands map to database operations already implemented in Phase 1.

**Delivers:**
- Message formatter with HTML parse_mode (more predictable than Markdown)
- send_long_message() helper (splits on article boundaries, adds [1/N] headers, handles 4096-char limit)
- Multi-user delivery (iterate over chat_ids from settings table)
- Briefing .md file saving to briefings/ folder
- Bot command handlers: /add_source, /remove_source, /list_sources, /add_keyword, /remove_keyword, /list_keywords, /add_global, /remove_global, /list_globals, /set_times, /enable_source, /disable_source, /briefing, /collect, /status, /help
- Deletion confirmation flow (/confirm_delete for destructive actions)
- Chat ID authorization (allow-list, reject unknown users)
- Command response formatting (always confirm current state after changes)

**Addresses:**
- Pitfall #6 (message length limit) — send_long_message() with splitting
- Security (chat_id validation) from pitfalls research

**Uses:** python-telegram-bot ConversationHandler for multi-step flows, formatting utilities

**Implements:** Telegram Bot Handlers, Message Sender from architecture

### Phase 5: Scheduling & Deployment
**Rationale:** Scheduler is the final integration piece that triggers the automated pipeline. Deployment requires everything working locally first. systemd configuration must handle restarts, logging, and watchdog from the start to avoid silent failures.

**Delivers:**
- JobQueue integration with briefing service (scheduled collection + briefing jobs)
- Dynamic schedule updates (set_times command modifies cron jobs without restart)
- KST timezone handling (Asia/Seoul, not UTC)
- deploy.sh rsync script for GCP deployment
- systemd service file (Restart=always, RestartSec=10, WatchdogSec=300)
- newsbot user creation (non-root execution)
- Structured logging (journald, greppable by source/phase)
- Health check heartbeat for systemd watchdog
- Graceful shutdown handler (SIGTERM -> flush DB, close connections)

**Addresses:**
- Pitfall #7 (silent service death) — systemd WatchdogSec + health check
- Timezone misconfiguration from pitfalls checklist
- Security (non-root execution)

**Uses:** APScheduler via JobQueue, systemd, GCP instance

**Implements:** Scheduler, deployment infrastructure from architecture

### Phase Ordering Rationale

- **Phase 1 first** because the async architecture (JobQueue vs separate scheduler) is a foundational decision that's expensive to change. SQLite WAL mode and error handling patterns established here prevent technical debt in all later phases.
- **Phase 2 second** because you need articles before you can summarize them. RSS before HTML because RSS is more reliable (stable contract vs fragile CSS selectors). Monitoring built from day one because HTML parsers WILL break.
- **Phase 3 third** because it depends on collected articles. The batching strategy (all articles in one prompt) must be designed before writing the first API call to avoid refactoring later.
- **Phase 4 fourth** because it consumes formatted briefings. Bot commands are thin wrappers over database CRUD, so they can be built in parallel with delivery if needed.
- **Phase 5 last** because it requires everything working locally. Scheduling is the orchestration layer that ties collection + summarization + delivery together.

**Key dependencies from research:**
- Collection -> Summarization (need articles to summarize)
- Summarization -> Delivery (need summaries to send)
- All commands -> Database (every command is a DB operation)
- Scheduler -> Briefing pipeline (orchestrates the full flow)
- Deployment -> Local validation (deploy after everything works)

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 2 (Collection):** HTML parsing is site-specific. The generic parser will work initially but expect to write custom per-source parsers. Each new source may need research on its specific HTML structure. Recommend `/gsd:research-phase` when adding sources beyond the initial 4 RSS feeds.
- **Phase 3 (Summarization):** Claude prompt engineering for Korean output quality and [keyword] tag extraction. May need iteration to get consistent formatting. Consider research if summaries are low quality.

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Foundation):** SQLite setup, aiosqlite usage, python-telegram-bot Application initialization are all well-documented with established patterns.
- **Phase 4 (Delivery):** Telegram bot command handlers are straightforward CRUD with telegram-bot library examples widely available.
- **Phase 5 (Deployment):** systemd service setup and rsync deployment are standard patterns for Python services.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies are mature, widely used, and well-documented. Version numbers are MEDIUM confidence (based on training data through early 2025), but minimum versions specified are conservative and safe. |
| Features | HIGH | Table stakes and anti-features based on well-established news aggregation domain patterns. SOP provides explicit requirements. Differentiators are inferred from SOP goals and competitive analysis. |
| Architecture | HIGH | Single-server async Python + SQLite + Telegram bot is a well-understood pattern. Component boundaries and data flow are standard for this domain. Event loop management is the main complexity, but python-telegram-bot JobQueue solves it cleanly. |
| Pitfalls | MEDIUM-HIGH | Based on domain knowledge of the libraries and common mistakes with async Python, SQLite concurrency, HTML scraping, and LLM API costs. No web search verification, but these are mature libraries with well-known failure modes documented in training data. |

**Overall confidence:** MEDIUM-HIGH

Research is comprehensive for architectural decisions and feature prioritization. Version numbers should be verified against PyPI before installation (pip index versions <package>), but minimum versions are conservative. The async architecture pattern (single event loop via JobQueue) is the critical insight that avoids the #1 pitfall.

### Gaps to Address

**During planning/execution:**

- **Exact library versions:** Training data cutoff is early 2025. Verify on PyPI: python-telegram-bot, anthropic SDK, httpx, feedparser, beautifulsoup4, lxml, APScheduler. The minimum versions specified are safe starting points.

- **Claude prompt engineering for Korean output:** The research assumes claude-sonnet-4-20250514 can produce quality Korean summaries. This should be validated in Phase 3 with sample articles. If quality is poor, iterate on prompt or consider adding translation step.

- **HTML parser resilience:** The generic BeautifulSoup4 approach will work for MVP but is fragile. Expect to write custom per-source parsers. Budget time in Phase 2 for parser debugging when adding new sources. Consider storing raw HTML snapshots for debugging.

- **GCP instance specs:** Research assumes a "small GCP instance" is sufficient. Specific CPU/memory requirements not researched. Recommend: 1 vCPU, 2GB RAM minimum (SQLite + Python + async concurrency is lightweight). Monitor and scale up if needed.

- **Telegram rate limits:** Research notes 30 messages/second limit. With 2-5 users, this is irrelevant. If scaling beyond 30 users, add per-user send delay. Document the limit in Phase 4 for future reference.

- **Korean news site robots.txt compliance:** Research recommends "respect robots.txt as a courtesy" but does not detail which Korean sites have strict crawling policies. Check robots.txt for each source in Phase 2 to avoid IP blocks.

## Sources

### Primary (HIGH confidence)
- **PROJECT.md** — project scope, constraints, team context
- **SOP v2.1** — detailed requirements, source list, feature specifications
- **Domain knowledge of Python news aggregation patterns** — RSS parsing, HTML scraping, deduplication, keyword filtering are well-established patterns
- **python-telegram-bot v20+ async architecture** — based on library documentation knowledge (v20 breaking changes to asyncio, JobQueue integration)
- **APScheduler v3 vs v4** — v4 rewrite status and API incompatibility widely documented in training data
- **SQLite concurrency (WAL mode)** — well-understood SQLite behavior, WAL mode benefits are official SQLite documentation

### Secondary (MEDIUM confidence)
- **Anthropic Python SDK retry behavior** — based on SDK patterns, not verified against current docs
- **feedparser bozo flag behavior** — long-standing feedparser feature, but edge cases may exist
- **Telegram Bot API message limits** — 4096-char limit is official, but specific handling of Markdown vs HTML escaping based on community knowledge
- **Korean news site encoding issues** — inferred from general Korean web encoding patterns (UTF-8 vs EUC-KR), not specific site research

### Tertiary (LOW confidence, needs validation)
- **Exact version numbers** — Training data through early 2025; live PyPI versions may differ. Minimum versions specified are conservative and should work, but latest stable should be verified.
- **GCP Python 3.12 availability** — Assumed based on Ubuntu LTS patterns. Verify GCP image options during deployment planning.
- **Claude prompt quality for Korean summarization** — Assumed based on general Claude multilingual capabilities. Needs validation with real articles in Phase 3.

---
*Research completed: 2026-03-26*
*Ready for roadmap: yes*
