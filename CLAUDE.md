<!-- GSD:project-start source:PROJECT.md -->
## Project

**News Briefing System (자동 뉴스 브리핑 시스템)**

IT/반도체/AI 뉴스 소스에서 기사를 자동 수집하고, 소스별 키워드 필터링 후 지정 시간에 Claude API로 한줄 요약 브리핑을 생성하여 텔레그램으로 전달하는 시스템. 소규모 팀(2-5명)이 공유 설정으로 각자 1:1 텔레그램 봇을 통해 동일한 브리핑을 수신한다. 모든 설정은 텔레그램 봇 채팅으로 관리한다.

**Core Value:** 뉴스 소스에서 키워드 기반으로 필터링된 기사를 정해진 시간에 한줄 요약으로 받아볼 수 있어야 한다 — 수집부터 요약, 전달까지 완전 자동화.

### Constraints

- **Tech Stack**: Python 3.11+, SQLite, APScheduler, python-telegram-bot, feedparser, BeautifulSoup4, Anthropic Claude API — SOP에서 지정
- **Summarization Model**: claude-sonnet-4-20250514 — Anthropic Claude API
- **Server**: GCP 인스턴스 34.172.56.22, Ubuntu, systemd 서비스
- **Deployment**: rsync 기반 로컬→서버 배포 (deploy.sh)
- **DB**: SQLite 단일 파일 (data/news.db) — 경량 개인/소팀용
- **Interface**: 텔레그램 봇이 유일한 사용자 인터페이스
- **API Keys**: Anthropic API 토큰 보유, Telegram Bot Token은 추후 발급
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## SOP Validation Summary
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
# Core dependencies
# Pin APScheduler to v3
# In requirements.txt:
# apscheduler>=3.10.0,<4.0.0
# Dev dependencies
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
- python-telegram-bot v20+ runs on asyncio
- Use httpx.AsyncClient for non-blocking HTTP fetches
- APScheduler 3.x supports AsyncIOScheduler that integrates with the asyncio event loop
- This means the entire application runs in a single async event loop: Telegram bot polling + scheduled news fetching + article parsing
# APScheduler's AsyncIOScheduler runs inside the same event loop
# as python-telegram-bot's Application
# The Telegram bot's Application.run_polling() drives the event loop
# APScheduler hooks into it
# Enable WAL mode for concurrent reads during writes
## Version Compatibility
| Package | Compatible With | Notes |
|---------|-----------------|-------|
| python-telegram-bot >=21.0 | Python 3.9+ | Fully async. Uses httpx internally. |
| APScheduler 3.10.x | Python 3.8+ | AsyncIOScheduler works with any asyncio event loop. |
| anthropic SDK >=0.40.0 | httpx >=0.27.0 | SDK depends on httpx; no need to install requests separately. |
| feedparser 6.x | Python 3.8+ | No external dependencies. |
| beautifulsoup4 4.12+ | lxml 5.x | Specify `features="lxml"` when creating BeautifulSoup. |
## Sources
- Training data knowledge of Python ecosystem through early 2025 (MEDIUM confidence on exact version numbers)
- APScheduler v3 vs v4 status: Based on pypi release history and GitHub discussions through early 2025 (HIGH confidence on "avoid v4" recommendation)
- python-telegram-bot async migration: Known breaking change in v20.0, stable in v21.x (HIGH confidence on async architecture)
- httpx as anthropic SDK dependency: Documented in anthropic SDK requirements (HIGH confidence)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

## Server & Deployment

### GCP 인스턴스 (34.172.56.22)
- **OS**: Ubuntu 24.04 LTS, Python 3.12.3
- **SSH**: `ssh -i ~/.ssh/gcp_rsa_34_172_56_22 awsmi@34.172.56.22`
- **배포 경로**: `/home/awsmi/news-briefing/`
- **서비스**: `news-briefing.service` (systemd, enabled, auto-restart)
- **배포 방법**: `scp -i ~/.ssh/gcp_rsa_34_172_56_22 -r src/ requirements.txt awsmi@34.172.56.22:~/news-briefing/` 후 `sudo systemctl restart news-briefing`
- **로그**: `~/news-briefing/logs/service.log`, `~/news-briefing/logs/service-error.log`

### 동일 서버 내 다른 봇 (충돌 금지)
- **dart-noti-bot**: DART 공시 알림 텔레그램 봇
  - 경로: `/opt/dart-noti-bot/`
  - 서비스: `dart-noti-bot.service` (User=awsmisojg)
  - 토큰: `8768...` (news-briefing 토큰 `8637...`과 다름)
- **절대 dart-noti-bot 서비스를 중지/재시작/수정해서는 안 됨**
- **배포 시 news-briefing 서비스만 restart할 것** (`sudo systemctl restart news-briefing`)
- 두 봇은 서로 다른 Telegram Bot Token을 사용하므로 polling 충돌 없음
- news-briefing 봇은 로컬과 서버에서 동시에 실행하면 안 됨 (같은 토큰으로 polling 충돌)

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
