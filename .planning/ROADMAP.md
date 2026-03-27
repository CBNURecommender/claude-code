# Roadmap: News Briefing System (자동 뉴스 브리핑 시스템)

## Overview

This roadmap delivers an automated news briefing system in 6 phases, following the data pipeline from storage through collection, summarization, bot interface, delivery, and deployment. Each phase builds on the previous: the database must exist before articles can be stored, articles must be collected before they can be summarized, summaries must exist before they can be delivered, and the bot must work locally before deploying to production. The system is fully operational after Phase 5 (local), and production-ready after Phase 6.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation & Database** - Async runtime, SQLite schema, logging, and configuration
- [ ] **Phase 2: Collection Engine** - RSS and HTML parsers with keyword filtering and deduplication
- [ ] **Phase 3: Summarization Pipeline** - Claude API integration with batched Korean summaries and briefing storage
- [ ] **Phase 4: Bot Interface & Source Management** - Telegram bot commands for source, keyword, and system management
- [ ] **Phase 5: Briefing Delivery & Scheduling** - Scheduled and on-demand briefing delivery to multiple users
- [ ] **Phase 6: Production Deployment** - systemd service, deploy script, and server configuration

## Phase Details

### Phase 1: Foundation & Database
**Goal**: The async runtime and data layer are operational, so all subsequent phases can store and retrieve data without architectural rework
**Depends on**: Nothing (first phase)
**Requirements**: INF-01, INF-02, INF-03, INF-04, INF-05, INF-06, DEP-05
**Success Criteria** (what must be TRUE):
  1. Running `python main.py` starts the python-telegram-bot Application with JobQueue on a single asyncio event loop without errors
  2. SQLite database file is created at `data/news.db` on first run with all 6 tables (sources, source_keywords, global_keywords, articles, briefings, settings) in WAL mode
  3. 13 initial news sources are auto-registered in the sources table on first run
  4. Application reads API keys and bot token from `.env` file and fails clearly if missing
  5. Log messages appear in `logs/` directory with structured format (timestamp, level, component)
**Plans:** 3 plans
Plans:
- [x] 01-01-PLAN.md — Project scaffolding, config loader, structured logging
- [x] 01-02-PLAN.md — Async SQLite database with 6 tables and 13 initial sources
- [x] 01-03-PLAN.md — Async main.py entry point wiring bot + DB + logging

### Phase 2: Collection Engine
**Goal**: The system can fetch articles from RSS and HTML sources, filter by keywords, and store them in the database without duplicates
**Depends on**: Phase 1
**Requirements**: SRC-05, COL-01, COL-02, COL-03, COL-04, COL-05, COL-06, COL-07, COL-08, KWD-06, KWD-07, KWD-08
**Success Criteria** (what must be TRUE):
  1. System auto-detects source type (RSS vs HTML) when a source URL is registered and fetches articles using the appropriate parser
  2. Articles are collected only from the exact registered URL, not from the site homepage or other pages
  3. Duplicate articles (same URL) are stored only once regardless of how many collection cycles run
  4. Articles matching per-source or global keywords (case-insensitive substring on titles) are stored with matched keywords as JSON; sources with 0 keywords collect all articles
  5. A single source failure (timeout, parse error) is logged and skipped without blocking other sources in the same collection cycle
**Plans:** 3 plans
Plans:
- [x] 02-01-PLAN.md — Source type auto-detector and keyword filter with unit tests
- [x] 02-02-PLAN.md — RSS parser, HTML parser, and collection orchestrator
- [x] 02-03-PLAN.md — Wire scheduled collection and /collect command into main.py

### Phase 3: Summarization Pipeline
**Goal**: Collected articles are summarized into Korean one-line briefings using Claude API and stored as .md files
**Depends on**: Phase 2
**Requirements**: SUM-01, SUM-02, SUM-03, SUM-04, SUM-05, STR-01, STR-02
**Success Criteria** (what must be TRUE):
  1. Running the briefing pipeline produces one-line Korean summaries in `[핵심키워드] 요약문 (출처)` format for each article, regardless of source language
  2. All pending articles are batched into a single Claude API call (not one call per article)
  3. Once summarized, articles are marked `is_briefed=1` and do not appear in the next briefing cycle
  4. If Claude API fails after retries, the briefing falls back to a raw article title list instead of failing silently
  5. Each briefing is saved as a .md file in `briefings/` with `YYYY-MM-DD_HH-MM.md` naming and recorded in the briefings DB table
**Plans**: TBD

### Phase 4: Bot Interface & Source Management
**Goal**: Users can manage all sources, keywords, and system settings through Telegram bot commands with clear Korean feedback
**Depends on**: Phase 1
**Requirements**: SRC-01, SRC-02, SRC-03, SRC-04, KWD-01, KWD-02, KWD-03, KWD-04, KWD-05, BOT-01, BOT-02, BOT-03, BOT-04, BOT-05
**Success Criteria** (what must be TRUE):
  1. User can add, remove, list, enable, and disable news sources via bot commands, with deletion requiring confirmation
  2. User can add, remove, list, and clear per-source keywords, and separately manage global keywords via bot commands
  3. /help shows all available commands with Korean descriptions; /status shows source count, pending articles, and briefing schedule
  4. All bot command responses provide clear success or error feedback in Korean
  5. Bot automatically captures and stores chat_id on first message from any new user
**Plans:** 3/4 plans executed
Plans:
- [x] 04-01-PLAN.md — DB query layer for sources, keywords, chat_ids, and counts
- [x] 04-02-PLAN.md — Source management commands (add, remove with confirm, list, enable, disable)
- [x] 04-03-PLAN.md — Keyword management commands (per-source and global)
- [ ] 04-04-PLAN.md — System commands (/help, /status, /list_times), chat_id auto-capture, handler wiring in main.py

### Phase 5: Briefing Delivery & Scheduling
**Goal**: Briefings are delivered to all team members at configured times, with on-demand triggers and dynamic schedule changes
**Depends on**: Phase 3, Phase 4
**Requirements**: DLV-01, DLV-02, DLV-03, DLV-04, DLV-05, DLV-06, DLV-07
**Success Criteria** (what must be TRUE):
  1. Briefing is automatically delivered as a Telegram message to all registered chat_ids at the user-configured times (KST timezone)
  2. User can set multiple briefing times via /set_times and the schedule takes effect immediately without restart
  3. User can trigger an immediate briefing via /briefing and an immediate collection via /collect
  4. When a briefing message exceeds 4096 characters, it is split across multiple messages with proper boundaries
  5. When no new articles exist at briefing time, a simple "no new articles" notification is sent (no .md file created)
**Plans:** 2 plans
Plans:
- [ ] 05-01-PLAN.md — Telegram delivery service with message splitting and multi-user delivery
- [ ] 05-02-PLAN.md — JobQueue scheduling, /set_times /briefing /collect handlers, main.py wiring

### Phase 6: Production Deployment
**Goal**: The system runs continuously on the GCP server with automatic restarts and safe deployment workflow
**Depends on**: Phase 5
**Requirements**: DEP-01, DEP-02, DEP-03, DEP-04
**Success Criteria** (what must be TRUE):
  1. Running `./deploy.sh` syncs code to GCP instance 34.172.56.22 via rsync, excluding .env, data/, briefings/, and logs/
  2. The system runs as a systemd service that auto-starts on server reboot and auto-restarts on crash
  3. After deployment, the bot responds to commands and delivers scheduled briefings on the server without manual intervention
**Plans:** 1 plan
Plans:
- [ ] 06-01-PLAN.md — systemd service file, deploy script, and .env.example

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6
Note: Phase 4 depends only on Phase 1, so it can execute in parallel with Phases 2-3 if needed.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Database | 0/3 | Planned | - |
| 2. Collection Engine | 0/3 | Planned | - |
| 3. Summarization Pipeline | 1/2 | In Progress|  |
| 4. Bot Interface & Source Management | 3/4 | In Progress|  |
| 5. Briefing Delivery & Scheduling | 0/2 | Planned | - |
| 6. Production Deployment | 0/1 | Planned | - |
