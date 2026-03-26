# Stack Research

**Domain:** Python-based news aggregation and automated briefing system
**Researched:** 2026-03-26
**Confidence:** MEDIUM (versions based on training data through early 2025; live PyPI verification unavailable)

## SOP Validation Summary

The SOP-specified stack is **well-chosen and appropriate** for this project scope. Every technology selection is defensible for a small-team, single-server news briefing system. Two adjustments are recommended: prefer `httpx` over `requests` (the Anthropic SDK already depends on it), and pin APScheduler to v3.x (v4 is a rewrite with breaking changes).

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Python | 3.11+ (use 3.12 if available on GCP) | Runtime | SOP-specified. 3.11 added ExceptionGroup and tomllib; 3.12 adds improved error messages and f-string improvements. Both are stable on Ubuntu LTS. | HIGH |
| SQLite | 3.x (system-bundled) | Database | Zero-config, single-file DB. Perfect for single-server, low-write-volume news storage. WAL mode handles the modest concurrency (scheduler writes + bot reads). No separate process to manage on GCP. | HIGH |
| Anthropic Python SDK | >=0.40.0 | Claude API client | Official SDK for Claude API access. Handles auth, retries, streaming. Required for claude-sonnet-4-20250514 model. | MEDIUM |
| python-telegram-bot | >=21.0 | Telegram bot interface | The mature, async-native Telegram library for Python. v20+ moved to fully async (asyncio). v21 is the current stable line. Comprehensive ConversationHandler for multi-step bot flows. | MEDIUM |

### Data Collection Libraries

| Library | Version | Purpose | Why Recommended | Confidence |
|---------|---------|---------|-----------------|------------|
| feedparser | >=6.0.11 | RSS/Atom feed parsing | The standard Python RSS parser. Handles malformed feeds gracefully, normalizes date formats across feed types. No real alternative exists in the Python ecosystem. | HIGH |
| beautifulsoup4 | >=4.12.0 | HTML parsing | Industry standard for HTML scraping. Forgiving parser that handles real-world broken HTML. Use with `lxml` backend for speed. | HIGH |
| lxml | >=5.0.0 | HTML/XML parser backend | 10-50x faster than Python's built-in html.parser. BeautifulSoup with lxml is the standard scraping combination. Also useful for XPath queries if needed. | HIGH |
| httpx | >=0.27.0 | HTTP client | **Recommended over `requests`.** The Anthropic SDK already depends on httpx, so it is a zero-cost addition. Supports async natively (critical since python-telegram-bot v20+ is async). Connection pooling, timeout configuration, HTTP/2 support. | MEDIUM |

### Scheduling and Infrastructure

| Library | Version | Purpose | Why Recommended | Confidence |
|---------|---------|---------|-----------------|------------|
| APScheduler | >=3.10.0, <4.0.0 | Job scheduling | **Pin to 3.x line.** v3 is battle-tested for cron-like scheduling in long-running processes. v4 is a major rewrite (alpha/beta quality) with incompatible API. CronTrigger handles "run at 08:00 KST" use case directly. | HIGH |
| python-dotenv | >=1.0.0 | Environment variable management | Simple .env file loading for API keys and tokens. No-dependency, no-config. Standard practice for 12-factor app config. | HIGH |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| ruff | Linter + formatter | Replaces flake8, isort, black in a single fast tool. Use `ruff check` and `ruff format`. |
| pytest | Testing | Standard Python test framework. Use with pytest-asyncio for async test support. |
| pytest-asyncio | Async test support | Required because python-telegram-bot v20+ and httpx are async. |

## Installation

```bash
# Core dependencies
pip install anthropic python-telegram-bot httpx feedparser beautifulsoup4 lxml apscheduler python-dotenv

# Pin APScheduler to v3
# In requirements.txt:
# apscheduler>=3.10.0,<4.0.0

# Dev dependencies
pip install ruff pytest pytest-asyncio
```

**requirements.txt:**
```
anthropic>=0.40.0
python-telegram-bot>=21.0
httpx>=0.27.0
feedparser>=6.0.11
beautifulsoup4>=4.12.0
lxml>=5.0.0
apscheduler>=3.10.0,<4.0.0
python-dotenv>=1.0.0
```

**requirements-dev.txt:**
```
ruff
pytest
pytest-asyncio
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| httpx | requests | Only if you need synchronous-only code and want the simplest possible HTTP. But since python-telegram-bot v20+ is async, httpx is the natural fit. requests has no async support. |
| APScheduler 3.x | APScheduler 4.x | Do NOT use 4.x yet. It is a ground-up rewrite, API is completely different, and it was still in alpha/beta as of early 2025. Wait for stable release. |
| APScheduler 3.x | Celery / Celery Beat | Only if you need distributed task queues across multiple workers. Massive overkill for a single-server cron-like scheduler. Requires Redis or RabbitMQ. |
| SQLite | PostgreSQL | Only if you need multi-server writes, full-text search at scale, or concurrent write-heavy workloads. This project has none of those needs. |
| beautifulsoup4 + lxml | Scrapy | Only if you need a full crawling framework with middleware, pipelines, rate limiting built in. Overkill for targeted URL parsing from 13 known sources. |
| beautifulsoup4 | selectolax / parsel | selectolax is faster but less forgiving with broken HTML. parsel (Scrapy's selector) is good but adds Scrapy dependency. BS4 is the safe default. |
| python-telegram-bot | aiogram | aiogram is a strong async Telegram framework. Choose it if you want a more "framework-like" approach. python-telegram-bot has broader community and documentation. Either works; SOP specifies python-telegram-bot, so stick with it. |
| Claude claude-sonnet-4-20250514 | GPT-4o-mini / Gemini | Claude sonnet is well-suited for summarization. The SOP specifies it, the team has API access. No reason to switch. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| requests (as primary HTTP) | No async support. python-telegram-bot v20+ is fully async; mixing sync requests with async code leads to blocking the event loop or needing run_in_executor hacks. | httpx (async-native, already a dependency of anthropic SDK) |
| APScheduler 4.x | API completely changed from v3. Was alpha/beta quality. Tutorials and Stack Overflow answers all reference v3 API. | APScheduler 3.10.x |
| newspaper3k / newspaper4k | Flaky article extraction, heavy dependencies, inconsistent with Korean news sites. Better to write targeted parsers with BS4. | beautifulsoup4 + lxml with custom extraction logic |
| Scrapy | Full crawling framework is overkill. Adds complexity (Twisted reactor, item pipelines, settings framework) for what is essentially "fetch 13 URLs and parse them." | httpx + beautifulsoup4 |
| aiohttp (as HTTP client) | Less ergonomic API than httpx, requires manual session management. httpx is the modern standard for async HTTP in Python. | httpx |
| schedule (the library) | Simple but no cron expression support, no persistence, no timezone handling. APScheduler is the standard for production scheduling. | APScheduler 3.x |
| SQLAlchemy | ORM is overkill for ~5 tables with simple queries. Raw sqlite3 module with well-structured helper functions is clearer and lighter. | Python built-in sqlite3 module |

## Stack Patterns

**Async Architecture (Recommended):**
- python-telegram-bot v20+ runs on asyncio
- Use httpx.AsyncClient for non-blocking HTTP fetches
- APScheduler 3.x supports AsyncIOScheduler that integrates with the asyncio event loop
- This means the entire application runs in a single async event loop: Telegram bot polling + scheduled news fetching + article parsing

**Key Pattern: Single Event Loop**
```python
# APScheduler's AsyncIOScheduler runs inside the same event loop
# as python-telegram-bot's Application
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
# The Telegram bot's Application.run_polling() drives the event loop
# APScheduler hooks into it
```

**SQLite WAL Mode:**
```python
# Enable WAL mode for concurrent reads during writes
import sqlite3
conn = sqlite3.connect("data/news.db")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA foreign_keys=ON")
```

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| python-telegram-bot >=21.0 | Python 3.9+ | Fully async. Uses httpx internally. |
| APScheduler 3.10.x | Python 3.8+ | AsyncIOScheduler works with any asyncio event loop. |
| anthropic SDK >=0.40.0 | httpx >=0.27.0 | SDK depends on httpx; no need to install requests separately. |
| feedparser 6.x | Python 3.8+ | No external dependencies. |
| beautifulsoup4 4.12+ | lxml 5.x | Specify `features="lxml"` when creating BeautifulSoup. |

**Critical Note:** python-telegram-bot v20+ already bundles httpx as a dependency. The anthropic SDK also depends on httpx. So httpx is effectively a transitive dependency you get for free -- use it directly instead of adding requests as another HTTP library.

## Sources

- Training data knowledge of Python ecosystem through early 2025 (MEDIUM confidence on exact version numbers)
- APScheduler v3 vs v4 status: Based on pypi release history and GitHub discussions through early 2025 (HIGH confidence on "avoid v4" recommendation)
- python-telegram-bot async migration: Known breaking change in v20.0, stable in v21.x (HIGH confidence on async architecture)
- httpx as anthropic SDK dependency: Documented in anthropic SDK requirements (HIGH confidence)

**Verification needed:** Before `pip install`, run `pip index versions <package>` or check pypi.org for each package to confirm latest stable versions. The minimum versions listed above are conservative and should be safe.

---
*Stack research for: Python news aggregation and briefing system*
*Researched: 2026-03-26*
