# Requirements: News Briefing System (자동 뉴스 브리핑 시스템)

**Defined:** 2026-03-26
**Core Value:** 뉴스 소스에서 키워드 기반으로 필터링된 기사를 정해진 시간에 한줄 요약으로 받아볼 수 있어야 한다

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Source Management (SRC)

- [x] **SRC-01**: User can add a news source with name and URL via Telegram bot command
- [x] **SRC-02**: User can remove a news source via Telegram bot command (with deletion confirmation)
- [x] **SRC-03**: User can list all registered sources with their status, URLs, and keyword counts
- [x] **SRC-04**: User can enable/disable a source without deleting it or its keywords
- [x] **SRC-05**: System auto-detects source type (RSS vs HTML) when a source is added

### Keyword Filtering (KWD)

- [x] **KWD-01**: User can add per-source filter keywords via Telegram bot command
- [x] **KWD-02**: User can remove per-source filter keywords via Telegram bot command
- [x] **KWD-03**: User can list keywords for a specific source
- [x] **KWD-04**: User can clear all keywords for a source (switches to collect-all mode)
- [x] **KWD-05**: User can add/remove/list global keywords that apply across all sources
- [x] **KWD-06**: Keyword matching is case-insensitive and partial substring match on article titles
- [x] **KWD-07**: Source with 0 keywords collects all articles; source with 1+ keywords filters by OR match
- [x] **KWD-08**: Global keywords combine with source keywords via OR condition

### Collection (COL)

- [x] **COL-01**: System collects articles from RSS sources using feedparser
- [x] **COL-02**: System collects articles from HTML sources using requests + BeautifulSoup4 generic parser
- [x] **COL-03**: System only parses the exact registered URL (not the site homepage)
- [x] **COL-04**: System prevents duplicate articles via URL-based deduplication
- [x] **COL-05**: System runs collection automatically at configurable intervals (default 30 min)
- [x] **COL-06**: User can trigger immediate collection via /collect command
- [x] **COL-07**: Individual source failure does not block other sources (log and skip)
- [x] **COL-08**: System stores matched keywords as JSON for each collected article

### Summarization (SUM)

- [x] **SUM-01**: System generates one-line summaries using Claude API in [핵심키워드] format
- [x] **SUM-02**: All summaries are in Korean regardless of source article language
- [x] **SUM-03**: Articles are batched into a single Claude API call per briefing cycle
- [x] **SUM-04**: Once an article is summarized, it is marked is_briefed=1 and excluded from future briefings
- [x] **SUM-05**: System falls back to raw article title list if Claude API fails after 3 retries

### Briefing Delivery (DLV)

- [ ] **DLV-01**: System delivers briefing as Telegram message at user-configured times (KST)
- [ ] **DLV-02**: User can set multiple briefing times via /set_times command
- [ ] **DLV-03**: Briefing time changes take effect immediately without restart
- [ ] **DLV-04**: User can trigger immediate briefing via /briefing command
- [ ] **DLV-05**: Messages exceeding 4096 characters are split across multiple Telegram messages
- [ ] **DLV-06**: When no new articles exist at briefing time, a simple notification is sent (no .md file)
- [ ] **DLV-07**: Briefing is delivered to all registered team members (multiple chat_ids, shared settings)

### Briefing Storage (STR)

- [x] **STR-01**: Each briefing is saved as a .md file in briefings/ folder with YYYY-MM-DD_HH-MM.md naming
- [x] **STR-02**: Briefing history is recorded in the briefings DB table (generated_at, article_count, file_path, delivered status)

### Bot Interface (BOT)

- [ ] **BOT-01**: /help command displays all available commands with descriptions
- [ ] **BOT-02**: /status command shows source count, pending article count, last/next briefing times
- [ ] **BOT-03**: /list_times command shows current briefing schedule
- [x] **BOT-04**: All bot commands provide clear success/error feedback messages in Korean
- [x] **BOT-05**: Bot automatically captures chat_id on first message from a user

### Infrastructure (INF)

- [x] **INF-01**: System runs as a single Python async process (bot + scheduler in one event loop)
- [x] **INF-02**: SQLite database with WAL mode for concurrent access safety
- [x] **INF-03**: All DB tables created on first run (sources, source_keywords, global_keywords, articles, briefings, settings)
- [x] **INF-04**: 13 initial news sources auto-registered on first run
- [x] **INF-05**: Configuration via .env file (API keys, bot token)
- [x] **INF-06**: Structured logging to logs/ directory

### Deployment (DEP)

- [ ] **DEP-01**: deploy.sh script syncs code to GCP instance (34.172.56.22) via rsync
- [ ] **DEP-02**: systemd service file for always-on operation with auto-restart
- [ ] **DEP-03**: Server reboot triggers automatic service start
- [ ] **DEP-04**: Deploy excludes .env, data/, briefings/, logs/ to preserve server state
- [x] **DEP-05**: .gitignore configured for Python, .env, data, briefings, logs

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Monitoring & Analytics

- **MON-01**: Briefing statistics (articles per source, keyword hit rates)
- **MON-02**: Source health monitoring (consecutive failure tracking, auto-disable)

### Enhanced Interaction

- **INT-01**: Article detail on demand (request more info about a briefing item via bot)
- **INT-02**: Past briefing search by keyword or date range via bot

### Advanced Collection

- **ADV-01**: Playwright integration for JavaScript-heavy sources
- **ADV-02**: Custom parsers for specific sources where generic parser fails

## Out of Scope

| Feature | Reason |
|---------|--------|
| Per-user source/keyword customization | Team shares settings; divergent preferences -> run separate instances |
| Real-time push notifications | Defeats "briefing" mental model; scheduled + on-demand sufficient |
| Full article content scraping | Copyright concerns, message size explosion, defeats one-line summary purpose |
| Web dashboard / admin UI | Telegram is the sole interface; web UI is over-engineering for 2-5 users |
| Sentiment analysis / categorization | Extra API cost, questionable accuracy for niche news; [keyword] tag sufficient |
| Email / Slack delivery | Team standardized on Telegram |
| ML relevance scoring | Requires training data infrastructure for 2-5 users; keyword filtering is debuggable |
| n8n / external automation | Pure Python; single codebase; no external dependencies |
| Mobile app | Telegram serves as the mobile interface |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SRC-01 | Phase 4 | Complete |
| SRC-02 | Phase 4 | Complete |
| SRC-03 | Phase 4 | Complete |
| SRC-04 | Phase 4 | Complete |
| SRC-05 | Phase 2 | Complete |
| KWD-01 | Phase 4 | Complete |
| KWD-02 | Phase 4 | Complete |
| KWD-03 | Phase 4 | Complete |
| KWD-04 | Phase 4 | Complete |
| KWD-05 | Phase 4 | Complete |
| KWD-06 | Phase 2 | Complete |
| KWD-07 | Phase 2 | Complete |
| KWD-08 | Phase 2 | Complete |
| COL-01 | Phase 2 | Complete |
| COL-02 | Phase 2 | Complete |
| COL-03 | Phase 2 | Complete |
| COL-04 | Phase 2 | Complete |
| COL-05 | Phase 2 | Complete |
| COL-06 | Phase 2 | Complete |
| COL-07 | Phase 2 | Complete |
| COL-08 | Phase 2 | Complete |
| SUM-01 | Phase 3 | Complete |
| SUM-02 | Phase 3 | Complete |
| SUM-03 | Phase 3 | Complete |
| SUM-04 | Phase 3 | Complete |
| SUM-05 | Phase 3 | Complete |
| DLV-01 | Phase 5 | Pending |
| DLV-02 | Phase 5 | Pending |
| DLV-03 | Phase 5 | Pending |
| DLV-04 | Phase 5 | Pending |
| DLV-05 | Phase 5 | Pending |
| DLV-06 | Phase 5 | Pending |
| DLV-07 | Phase 5 | Pending |
| STR-01 | Phase 3 | Complete |
| STR-02 | Phase 3 | Complete |
| BOT-01 | Phase 4 | Pending |
| BOT-02 | Phase 4 | Pending |
| BOT-03 | Phase 4 | Pending |
| BOT-04 | Phase 4 | Complete |
| BOT-05 | Phase 4 | Complete |
| INF-01 | Phase 1 | Complete |
| INF-02 | Phase 1 | Complete |
| INF-03 | Phase 1 | Complete |
| INF-04 | Phase 1 | Complete |
| INF-05 | Phase 1 | Complete |
| INF-06 | Phase 1 | Complete |
| DEP-01 | Phase 6 | Pending |
| DEP-02 | Phase 6 | Pending |
| DEP-03 | Phase 6 | Pending |
| DEP-04 | Phase 6 | Pending |
| DEP-05 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 46 total
- Mapped to phases: 46
- Unmapped: 0

---
*Requirements defined: 2026-03-26*
*Last updated: 2026-03-26 after roadmap creation*
