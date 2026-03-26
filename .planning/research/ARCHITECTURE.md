# Architecture Research

**Domain:** Automated news aggregation + AI summarization + Telegram bot delivery
**Researched:** 2026-03-26
**Confidence:** HIGH (well-understood domain, established libraries, clear constraints from PROJECT.md)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Telegram Bot Interface                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Command       │  │ Callback     │  │ Message      │          │
│  │ Handlers      │  │ Handlers     │  │ Sender       │          │
│  └──────┬───────┘  └──────┬───────┘  └──────▲───────┘          │
├─────────┴──────────────────┴─────────────────┴──────────────────┤
│                     Application Core                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Scheduler     │  │ Briefing     │  │ Config       │          │
│  │ (APScheduler) │  │ Service      │  │ Manager      │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                  │                   │
│         ▼                 ▼                  │                   │
│  ┌──────────────┐  ┌──────────────┐         │                   │
│  │ Collector     │  │ Summarizer   │         │                   │
│  │ Service       │  │ (Claude API) │         │                   │
│  └──────┬───────┘  └──────┬───────┘         │                   │
├─────────┴──────────────────┴─────────────────┴──────────────────┤
│                     Data & Parsing Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ RSS Parser    │  │ HTML Parser  │  │ Database     │          │
│  │ (feedparser)  │  │ (BS4+httpx)  │  │ (SQLite)     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Command Handlers** | Parse Telegram bot commands (`/add_source`, `/keywords`, `/schedule`, etc.), validate input, delegate to services | python-telegram-bot `CommandHandler` with `ConversationHandler` for multi-step flows |
| **Message Sender** | Format and deliver briefings to all registered chat_ids | python-telegram-bot `Bot.send_message()` with Markdown formatting, message splitting for long content |
| **Scheduler** | Trigger collection and briefing at configured times | APScheduler `AsyncIOScheduler` with `CronTrigger`, jobs stored in memory (not DB — simple enough) |
| **Briefing Service** | Orchestrate the full pipeline: collect -> filter -> summarize -> deliver -> mark as sent | Pure Python orchestrator class, the "brain" of the system |
| **Config Manager** | Read/write shared settings (sources, keywords, schedule times, chat_ids) | Thin wrapper over DB queries, caches in memory, invalidates on write |
| **Collector Service** | Fetch articles from all registered sources, apply keyword filters, deduplicate | Dispatches to RSS or HTML parser based on source type, stores raw articles in DB |
| **RSS Parser** | Parse RSS/Atom feeds | feedparser library — handles encoding, date parsing, feed variants |
| **HTML Parser** | Scrape article listings from web pages | httpx (async HTTP) + BeautifulSoup4, generic extractor with optional per-source overrides |
| **Summarizer** | Generate one-line Korean summaries for filtered articles | Anthropic Python SDK, batch articles into a single prompt, returns structured summaries |
| **Database** | Persist sources, articles, keywords, settings, briefing history | SQLite via `aiosqlite` for async compatibility with python-telegram-bot v20+ |

## Recommended Project Structure

```
news_briefing/
├── bot/                    # Telegram bot interface
│   ├── __init__.py
│   ├── handlers.py         # Command and callback handlers
│   ├── commands.py         # Command definitions and registration
│   └── formatting.py       # Message formatting utilities
├── core/                   # Business logic (no framework dependencies)
│   ├── __init__.py
│   ├── briefing.py         # Briefing pipeline orchestration
│   ├── collector.py        # Article collection orchestrator
│   ├── summarizer.py       # Claude API summarization
│   └── scheduler.py        # APScheduler setup and job management
├── parsers/                # News source parsing
│   ├── __init__.py
│   ├── base.py             # Abstract parser interface
│   ├── rss_parser.py       # RSS/Atom feed parser
│   ├── html_parser.py      # Generic HTML scraper
│   └── custom/             # Per-source custom parsers (added as needed)
│       └── __init__.py
├── db/                     # Database layer
│   ├── __init__.py
│   ├── models.py           # Table definitions / schema
│   ├── repository.py       # CRUD operations (single file is fine for this scale)
│   └── migrations.py       # Schema versioning (simple version table + SQL scripts)
├── config.py               # Environment variables, constants
├── main.py                 # Entry point — wire everything together
└── requirements.txt
data/
├── news.db                 # SQLite database (gitignored)
briefings/                  # Saved briefing .md files (R9)
deploy.sh                   # rsync deployment script
.env                        # API keys (gitignored)
```

### Structure Rationale

- **bot/:** Isolates Telegram-specific code. If you ever swap to Slack or another interface, only this folder changes. Handlers should be thin — validate input, call core services, format response.
- **core/:** Framework-agnostic business logic. The briefing pipeline, collection logic, and summarization are independent of Telegram. This makes them testable without mocking Telegram.
- **parsers/:** Separate from core because parsing is the most likely area to grow. New sources may need custom parsers. The `base.py` abstract class lets you add parsers without changing the collector.
- **db/:** Single repository file is appropriate for SQLite at this scale. Splitting into per-entity repositories would be over-engineering for 5-6 tables.

## Architectural Patterns

### Pattern 1: Pipeline Orchestration (Briefing Service)

**What:** The briefing service runs a sequential pipeline: collect articles -> filter by keywords -> summarize with Claude -> format message -> deliver to all chat_ids -> mark articles as sent -> save .md file.
**When to use:** Every scheduled briefing trigger.
**Trade-offs:** Simple and debuggable. Each step can fail independently and be retried. Downside: the whole pipeline is synchronous in sequence (each step waits for the previous), but that is fine for a system running 2-3 times per day.

**Example:**
```python
class BriefingService:
    async def run_briefing(self) -> BriefingResult:
        # 1. Collect new articles from all sources
        articles = await self.collector.collect_all()

        # 2. Filter by source-specific keywords
        filtered = self.filter_by_keywords(articles)

        if not filtered:
            return BriefingResult(skipped=True, reason="No new articles matched filters")

        # 3. Summarize with Claude API
        summaries = await self.summarizer.summarize(filtered)

        # 4. Format briefing message
        message = self.formatter.format_briefing(summaries)

        # 5. Deliver to all registered chat_ids
        await self.sender.broadcast(message)

        # 6. Mark articles as sent (so they are excluded next time — R7)
        await self.repository.mark_as_briefed(filtered)

        # 7. Save to .md file (R9)
        self.save_briefing_file(message)

        return BriefingResult(articles=len(filtered), delivered=True)
```

### Pattern 2: Parser Strategy (Source Type Dispatch)

**What:** A base parser interface with concrete implementations for RSS and HTML. The collector checks source type and dispatches to the right parser. Custom per-source parsers can override the generic HTML parser.
**When to use:** Every time articles are collected from a source.
**Trade-offs:** Clean extensibility — adding a new source type or custom parser requires no changes to existing code. Slight indirection, but worth it because HTML parsing is fragile and will need per-source tweaks.

**Example:**
```python
from abc import ABC, abstractmethod

class BaseParser(ABC):
    @abstractmethod
    async def parse(self, source: Source) -> list[Article]:
        """Fetch and parse articles from a source."""
        ...

class RSSParser(BaseParser):
    async def parse(self, source: Source) -> list[Article]:
        feed = feedparser.parse(await self.fetch(source.url))
        return [self._to_article(entry, source) for entry in feed.entries]

class HTMLParser(BaseParser):
    async def parse(self, source: Source) -> list[Article]:
        html = await self.fetch(source.url)
        soup = BeautifulSoup(html, "html.parser")
        # Generic extraction logic — works for most news listing pages
        return self._extract_articles(soup, source)

def get_parser(source: Source) -> BaseParser:
    if source.parser_type == "rss":
        return RSSParser()
    elif source.custom_parser:
        return load_custom_parser(source.custom_parser)
    return HTMLParser()
```

### Pattern 3: Shared Settings with Bot Commands

**What:** All settings (sources, keywords, schedule times, chat_ids) live in SQLite and are managed exclusively through Telegram bot commands. Settings are shared across all users — there is no per-user configuration.
**When to use:** All configuration operations.
**Trade-offs:** Single source of truth in DB. Bot commands are the only write path, which simplifies the system (no config files to sync, no web UI). Downside: if the bot is down, you cannot change settings (acceptable for this use case).

**Example:**
```python
# In bot/handlers.py
async def add_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = context.args[0] if context.args else None
    if not url:
        await update.message.reply_text("Usage: /add_source <url>")
        return

    source_type = await detect_source_type(url)  # Check if RSS or HTML
    await repository.add_source(url=url, source_type=source_type)
    await update.message.reply_text(f"Added: {url} (type: {source_type})")
```

## Data Flow

### Scheduled Briefing Flow (Primary)

```
APScheduler CronTrigger fires
    |
    v
BriefingService.run_briefing()
    |
    v
CollectorService.collect_all()
    |
    +---> For each Source in DB:
    |       |
    |       v
    |     get_parser(source) --> RSSParser or HTMLParser
    |       |
    |       v
    |     Fetch URL (httpx) --> Parse articles --> Store in DB
    |       |
    |       v
    |     Filter: keyword match? already briefed? --> filtered articles
    |
    v
Summarizer.summarize(filtered_articles)
    |
    v
Claude API call (batch prompt with all articles)
    |
    v
Format briefing message (Markdown)
    |
    +---> Send to each chat_id via Telegram Bot API
    |
    +---> Save to briefings/YYYY-MM-DD_HH-MM.md
    |
    v
Mark articles as briefed in DB
```

### Bot Command Flow (Configuration)

```
User sends /add_source https://example.com/feed
    |
    v
python-telegram-bot dispatches to add_source handler
    |
    v
Handler validates URL, detects source type (RSS vs HTML)
    |
    v
Repository.add_source() --> INSERT into sources table
    |
    v
Reply to user: "Source added (RSS detected)"
```

### Key Data Flows

1. **Collection flow:** Scheduler -> Collector -> Parser(s) -> DB. Articles flow inward from external sources into the database. Each article gets a unique hash (URL or title+date) to prevent duplicates.
2. **Briefing flow:** DB (unread articles) -> Filter (keyword match) -> Claude API (summarization) -> Telegram (delivery) + filesystem (.md save). Data flows outward from the database to users.
3. **Config flow:** Telegram command -> Handler -> DB write. Always user-initiated, always through bot commands, always to SQLite.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 2-5 users, 13 sources | Current design. SQLite, single process, APScheduler in-memory. No changes needed. |
| 10-20 users, 50 sources | Still fine with SQLite. May need to parallelize HTTP fetches (already async with httpx). Consider rate limiting to avoid IP blocks from news sites. |
| 50+ users, 100+ sources | Outgrowing this architecture. Would need PostgreSQL, a proper task queue (Celery), and possibly separate worker processes. But this is explicitly out of scope. |

### Scaling Priorities

1. **First bottleneck: HTTP fetch time.** Fetching 13 sources sequentially could take 30-60 seconds. Use `asyncio.gather()` with concurrency limit (e.g., 5 concurrent fetches) from day one. This is cheap to implement and prevents the briefing pipeline from being slow.
2. **Second bottleneck: Claude API latency.** A single summarization call with 20-30 articles takes 5-15 seconds. Acceptable. If article counts grow large, batch into multiple API calls of 15-20 articles each.
3. **Third bottleneck: Telegram rate limits.** Telegram allows ~30 messages/second to different chats. With 2-5 users, this is irrelevant. If scaling beyond 30 users, add a small delay between sends.

## Anti-Patterns

### Anti-Pattern 1: Mixing Bot Handlers with Business Logic

**What people do:** Put collection logic, filtering, and summarization directly inside Telegram command handlers or callback functions.
**Why it is wrong:** Makes the code untestable without mocking Telegram. Makes it impossible to run the briefing pipeline from anywhere except a Telegram trigger. Creates a tangled mess when handlers grow complex.
**Do this instead:** Handlers should be 5-15 lines: validate input, call a service method, format and return the response. All logic lives in `core/`.

### Anti-Pattern 2: Storing Configuration in Files

**What people do:** Use JSON/YAML config files for sources, keywords, and schedule settings alongside the database.
**Why it is wrong:** Two sources of truth. Bot commands modify one (DB), manual edits modify the other (file). They drift apart. Deployment overwrites config files.
**Do this instead:** SQLite is the single source of truth for all configuration. The only file-based config should be `.env` for secrets (API keys, bot token) and immutable settings (DB path).

### Anti-Pattern 3: Synchronous HTTP in an Async Bot

**What people do:** Use `requests` library for HTTP fetches inside an async python-telegram-bot v20+ application.
**Why it is wrong:** python-telegram-bot v20+ is fully async (built on `asyncio`). Using synchronous `requests` blocks the event loop, freezing the bot during article collection. The bot becomes unresponsive to commands while fetching sources.
**Do this instead:** Use `httpx.AsyncClient` for all HTTP requests. It has a nearly identical API to `requests` but is async-native.

### Anti-Pattern 4: One Claude API Call Per Article

**What people do:** Send each article to Claude individually for summarization.
**Why it is wrong:** 20 articles = 20 API calls = slow, expensive, and rate-limit-prone. Each call has ~1-2 seconds of overhead.
**Do this instead:** Batch articles into a single prompt. Send all filtered articles in one API call with instructions to return a structured list of summaries. One call for 20 articles takes roughly the same time as one call for 1 article.

### Anti-Pattern 5: No Deduplication Strategy

**What people do:** Only check article URL for duplicates.
**Why it is wrong:** Some sites change URL parameters (tracking codes, pagination), resulting in duplicate articles with different URLs. Some RSS feeds update the same article's entry with a new published date.
**Do this instead:** Use a composite deduplication key: normalized URL (strip query params) + title hash. Store the hash in the DB and check before inserting.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **News sources (RSS)** | feedparser library, async HTTP fetch | feedparser handles encoding, bozo feeds, date normalization. Feed URL may redirect — follow redirects. |
| **News sources (HTML)** | httpx + BeautifulSoup4 | Set a browser-like User-Agent header. Some sites block default Python UA. Respect robots.txt as a courtesy. Sites may change HTML structure — parsers will break. |
| **Anthropic Claude API** | anthropic Python SDK, async client | Use `claude-sonnet-4-20250514` as specified. Implement retry with exponential backoff for 429/500 errors. Set a reasonable `max_tokens` (2000-3000 for a batch of 20 summaries). |
| **Telegram Bot API** | python-telegram-bot v20+ (async) | Long polling mode (not webhooks) — simpler for single-server deployment. Register handlers in `main.py`. Use `Markdown` or `MarkdownV2` parse mode for formatting. |
| **GCP Instance** | systemd service | `ExecStart=/usr/bin/python3 /path/to/main.py`. Set `Restart=always`, `RestartSec=10`. Log to journald. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| bot/ <-> core/ | Direct async function calls | Handlers import and call service methods. Services never import from bot/. |
| core/ <-> parsers/ | Strategy pattern via BaseParser | Collector calls `parser.parse(source)`. Parser returns `list[Article]` dataclass. |
| core/ <-> db/ | Repository pattern | Services call `repository.method()`. Repository returns domain objects, never raw SQL rows. |
| Scheduler <-> BriefingService | APScheduler job callback | Scheduler calls `briefing_service.run_briefing()` as a scheduled job. |
| BriefingService <-> Telegram | Via MessageSender | BriefingService calls `sender.broadcast(message)`. Sender handles splitting long messages and per-chat delivery. |

## Suggested Build Order

Based on component dependencies, the recommended build order is:

1. **Database layer + models** — Everything depends on data storage. Define schema, create repository with CRUD operations. Can be tested independently.
2. **Parsers (RSS first, then HTML)** — RSS is simpler and more reliable. Get the collection pipeline working with RSS sources first. HTML parsing is more fragile and can come second.
3. **Collector service** — Depends on parsers and DB. Orchestrates fetching from all sources, deduplication, keyword filtering, and storage.
4. **Summarizer** — Depends on DB (reads articles). Isolated Claude API integration. Can be tested with sample articles.
5. **Briefing service** — Depends on collector, summarizer, and DB. The pipeline orchestrator that ties collection through delivery.
6. **Bot handlers** — Depends on core services and DB. Build command handlers for source management, keyword management, schedule management.
7. **Scheduler integration** — Depends on briefing service and bot. Wire APScheduler into the bot application lifecycle.
8. **Message delivery + .md saving** — Depends on briefing service output. Format and send to Telegram, save to filesystem.
9. **systemd deployment** — Depends on everything working locally. deploy.sh, service file, environment configuration on GCP.

**Key dependency insight:** The DB layer and parsers have zero upstream dependencies and can be built and tested first. The bot handlers and scheduler are "leaf" components that consume services — build them last.

## Sources

- PROJECT.md constraints (stack is fully specified: Python 3.11+, SQLite, APScheduler, python-telegram-bot, feedparser, BeautifulSoup4, Anthropic Claude API)
- python-telegram-bot v20+ is async-first (asyncio-based), which drives the choice of async HTTP client and async SQLite
- APScheduler 3.x uses `AsyncIOScheduler` for async compatibility
- Standard patterns for Python news aggregation systems based on domain knowledge (HIGH confidence — well-established patterns)

---
*Architecture research for: Automated News Briefing System*
*Researched: 2026-03-26*
