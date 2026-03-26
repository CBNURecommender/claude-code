# Feature Research

**Domain:** Automated news aggregation and briefing system (IT/semiconductor/AI niche)
**Researched:** 2026-03-26
**Confidence:** MEDIUM (based on domain knowledge of news aggregation systems; no web search verification available)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = system feels broken or unusable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Multi-source RSS collection | Core function -- system must pull from multiple feeds reliably | LOW | feedparser handles this well. SOP defines 4 RSS sources in Tier 1 |
| HTML page scraping for non-RSS sources | Many Korean news sites lack RSS; scraping is the only option | MEDIUM | Generic parser approach is correct for MVP. Expect 2-3 sources to need custom parsers post-launch |
| Source type auto-detection | Users should not need to know if a URL is RSS or HTML | LOW | Check URL patterns + Content-Type header. SOP already specifies this |
| Per-source keyword filtering | Core value prop -- users need signal from noise | LOW | Simple substring match on titles. SOP specifies case-insensitive partial match |
| Scheduled briefing delivery | The whole point -- automated delivery at set times | MEDIUM | APScheduler cron jobs. Must survive dynamic time changes without restart |
| AI-powered summarization | One-line summaries are the core differentiator over raw feed readers | MEDIUM | Claude API call with structured prompt. Must handle API failures gracefully |
| Duplicate article prevention | Users must not see the same article twice across briefings | LOW | URL-based dedup on collection + is_briefed flag for briefing exclusion |
| Telegram bot as control interface | SOP mandates this as the sole UI. Must feel responsive and complete | MEDIUM | python-telegram-bot v21+. All CRUD operations via chat commands |
| Source CRUD via bot | Users need to add/remove sources without touching config files | LOW | Standard DB operations behind bot command handlers |
| Keyword CRUD via bot | Dynamic keyword management is a core requirement | LOW | CRUD on source_keywords table |
| Briefing time configuration | Users must control when they receive briefings | LOW | Update DB setting + refresh scheduler jobs |
| Status/health check command | Users need to know the system is alive and working | LOW | /status showing source count, pending articles, next briefing time |
| On-demand briefing trigger | Users sometimes want a briefing NOW, not at the next scheduled time | LOW | /briefing command that runs the summarization pipeline immediately |
| On-demand collection trigger | Users want to force-collect before triggering a briefing | LOW | /collect command that runs all collectors immediately |
| Briefing history persistence | Briefings saved as .md files provide an archive users can reference | LOW | Write markdown to briefings/ folder with timestamp filename |
| Error resilience per source | One broken source must not block the entire collection cycle | LOW | try/except per source in collection loop, log and continue |
| Multi-user delivery | Team members each receive the same briefing via their own chat | LOW | Store multiple chat_ids, iterate on delivery |

### Differentiators (Competitive Advantage)

Features that make this system notably better than a basic RSS reader or manual news checking.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Korean + English unified summarization | All summaries in Korean regardless of source language -- eliminates language switching friction for the team | LOW | Claude handles multilingual input natively. Just specify output language in prompt |
| [Keyword] tag in summaries | Quick visual scanning -- users see topic at a glance without reading the full line | LOW | Part of the Claude summarization prompt format |
| Global keywords (cross-source) | Catch important topics regardless of which source publishes them | LOW | OR condition with source-specific keywords. SOP already defines this |
| Source enable/disable without deletion | Temporarily mute a noisy source without losing its keyword config | LOW | enabled flag in sources table. SOP already specifies this |
| Briefing file as markdown archive | Team can grep/search past briefings offline; version-controllable | LOW | Already in SOP. Valuable for long-term trend tracking |
| Confirmation step on destructive actions | Prevents accidental source deletion that would also cascade-delete keywords | LOW | SOP specifies /confirm_delete flow for /remove_source |
| Zero-article notification | Users know the system is alive even when there is nothing new | LOW | "No new articles" message at briefing time instead of silence |
| Message splitting for long briefings | Telegram has 4096-char limit; system must handle large briefing days | LOW | Split by article boundaries, not mid-sentence |
| Matched keyword tracking | Each article records which keywords matched it, enabling future analysis | LOW | stored as JSON in matched_keywords column |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems for this specific use case.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Per-user source/keyword customization | "I want different news than my teammate" | Massive complexity increase for 2-5 users. Shared team context is the actual value. If preferences diverge significantly, run two bot instances | Keep shared settings. SOP explicitly scopes this out |
| Real-time push notifications | "I want breaking news immediately" | Requires constant polling (expensive), notification fatigue, defeats the "briefing" mental model of batched digests | Scheduled briefings + /briefing for on-demand. If truly urgent, users check sources directly |
| Full article content scraping | "I want to read the whole article in Telegram" | Legal gray area (copyright), message size explosion, many sites block full scraping, defeats the purpose of one-line summaries | One-line summary + source link. Users click through for detail |
| Web dashboard / admin UI | "A web interface would be nicer" | Doubles the surface area. Telegram IS the interface. A dashboard for 2-5 users is over-engineering | Telegram bot commands cover all admin needs |
| Sentiment analysis / categorization | "Tag articles as positive/negative or by category" | Extra API cost, questionable accuracy for niche semiconductor news, adds complexity without clear action from users | The [keyword] tag in summaries already provides topical grouping |
| Email / Slack delivery channels | "What if someone doesn't use Telegram?" | Multi-channel delivery multiplies integration complexity. SOP explicitly chose Telegram-only | Team standardizes on Telegram |
| Machine learning for relevance scoring | "AI should learn what I find interesting" | Requires training data, feedback loop infrastructure, model management -- all for 2-5 users. Keyword filtering is deterministic and debuggable | Explicit keyword filtering. Users add/remove keywords to tune |
| Article deduplication by content similarity | "Different sources report the same news" | Requires NLP/embedding infrastructure, fuzzy matching is error-prone, and for a small team the occasional duplicate from different sources provides multiple perspectives | URL-based dedup is sufficient. Cross-source duplicates are acceptable -- different sources may have different angles |
| n8n or external automation integration | "Use n8n for workflow orchestration" | External dependency, another system to maintain, debugging across systems. SOP explicitly excludes this | Pure Python implementation. All logic in one codebase |
| Playwright/browser automation for all sources | "Some sites need JavaScript rendering" | Heavy dependency, slow, resource-intensive on a small GCP instance. Most news listing pages work fine with requests | Use requests + BS4 by default. Add Playwright only if a specific high-value source absolutely requires it |

## Feature Dependencies

```
[DB Schema + CRUD]
    |-- requires --> [Source Management Bot Commands]
    |                    |-- requires --> [Keyword Management Bot Commands]
    |                    |-- requires --> [Source Enable/Disable]
    |
    |-- requires --> [RSS Collector]
    |-- requires --> [HTML Collector]
    |                    |-- both require --> [Source Type Auto-Detection]
    |                    |-- both require --> [Keyword Filter]
    |                                            |-- requires --> [Global Keywords]
    |
    |-- requires --> [Article Storage + Dedup]
    |                    |-- requires --> [Briefing Generation (Claude API)]
    |                                        |-- requires --> [MD File Saving]
    |                                        |-- requires --> [Telegram Delivery]
    |                                        |-- requires --> [is_briefed Flag Update]
    |
    |-- requires --> [Settings Storage]
                         |-- requires --> [Scheduler (APScheduler)]
                         |                    |-- requires --> [Dynamic Time Update]
                         |
                         |-- requires --> [Briefing Time Bot Commands]

[Telegram Bot Framework]
    |-- requires --> [All Bot Commands]
    |-- requires --> [Multi-user Delivery]

[All of the above]
    |-- requires --> [main.py Integration (bot + scheduler)]
                         |-- requires --> [Deployment (systemd + deploy.sh)]
```

### Dependency Notes

- **DB Schema is the foundation:** Every component reads from or writes to SQLite. Must be solid before anything else.
- **Collectors require keyword filter:** Collection and filtering are tightly coupled -- an article that does not pass the filter should never be stored.
- **Briefing generation requires articles:** The summarizer pulls is_briefed=0 articles, so the collection pipeline must be working first.
- **Bot commands require DB CRUD:** Every bot command maps to a database operation. database.py must be complete before bot handlers.
- **Scheduler requires both collectors and summarizer:** It orchestrates the two main jobs (collect + brief).
- **Deployment is last:** Everything must work locally before deploying to GCP.

## MVP Definition

### Launch With (v1)

Minimum viable product -- what is needed to validate the concept works end-to-end.

- [x] DB schema initialization (all 6 tables) -- foundation for everything
- [x] RSS collector with feedparser -- covers Tier 1 sources immediately
- [x] Generic HTML collector with BS4 -- covers Tier 2 sources
- [x] Source type auto-detection -- seamless source addition
- [x] Per-source keyword filtering -- core signal-from-noise feature
- [x] Claude API one-line summarization -- core value proposition
- [x] Telegram briefing delivery -- the output channel
- [x] Scheduled collection + briefing (APScheduler) -- automation
- [x] Essential bot commands: /add_source, /remove_source, /list_sources, /add_keyword, /remove_keyword, /list_keywords, /set_times, /briefing, /collect, /status, /help -- minimum control surface
- [x] Duplicate prevention (URL-based) -- prevents noise
- [x] is_briefed flag management -- prevents re-summarizing
- [x] MD file saving -- briefing archive
- [x] Multi-user delivery -- team must all receive briefings

### Add After Validation (v1.x)

Features to add once core pipeline is confirmed working with real sources.

- [ ] Source enable/disable (/enable_source, /disable_source) -- triggered when a source becomes temporarily unreliable
- [ ] Global keywords (/add_global, /remove_global, /list_globals) -- triggered when team realizes some keywords should apply everywhere
- [ ] Deletion confirmation flow (/confirm_delete) -- triggered after first accidental deletion
- [ ] Message splitting for 4096-char limit -- triggered when briefing exceeds single message (likely with 10+ articles)
- [ ] Zero-article notification -- triggered when team wonders "is the system still running?"
- [ ] Custom parsers for specific broken sources -- triggered when generic HTML parser fails on a high-value source

### Future Consideration (v2+)

Features to defer until the system has been running for weeks and real usage patterns emerge.

- [ ] Briefing statistics (articles per source, keyword hit rates) -- useful for tuning keywords, but not needed until the system has been running long enough to generate meaningful data
- [ ] Article content preview on demand -- let users request more detail about a specific briefing item via bot interaction
- [ ] Briefing search/recall -- query past briefings by keyword or date range via bot
- [ ] Source health monitoring -- track consecutive failures per source, auto-disable after N failures
- [ ] Playwright integration for JS-heavy sources -- only if a critical source absolutely requires it

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| DB schema + CRUD | HIGH | LOW | P1 |
| RSS collector | HIGH | LOW | P1 |
| HTML collector (generic) | HIGH | MEDIUM | P1 |
| Source type auto-detection | MEDIUM | LOW | P1 |
| Per-source keyword filtering | HIGH | LOW | P1 |
| Claude API summarization | HIGH | MEDIUM | P1 |
| Telegram delivery | HIGH | LOW | P1 |
| APScheduler integration | HIGH | MEDIUM | P1 |
| Source CRUD bot commands | HIGH | LOW | P1 |
| Keyword CRUD bot commands | HIGH | LOW | P1 |
| Briefing time commands | HIGH | LOW | P1 |
| Instant trigger commands | MEDIUM | LOW | P1 |
| /status command | MEDIUM | LOW | P1 |
| /help command | LOW | LOW | P1 |
| MD file saving | MEDIUM | LOW | P1 |
| Multi-user delivery | HIGH | LOW | P1 |
| Duplicate prevention | HIGH | LOW | P1 |
| is_briefed management | HIGH | LOW | P1 |
| Source enable/disable | MEDIUM | LOW | P2 |
| Global keywords | MEDIUM | LOW | P2 |
| Deletion confirmation | LOW | LOW | P2 |
| Message splitting (4096 limit) | MEDIUM | LOW | P2 |
| Zero-article notification | LOW | LOW | P2 |
| Custom source parsers | MEDIUM | MEDIUM | P2 |
| Briefing statistics | LOW | MEDIUM | P3 |
| Article detail on demand | LOW | MEDIUM | P3 |
| Past briefing search | LOW | MEDIUM | P3 |
| Source health monitoring | MEDIUM | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch -- the system does not work without it
- P2: Should have, add when the specific trigger condition occurs
- P3: Nice to have, consider after weeks of real usage

## Competitor Feature Analysis

| Feature | Feedly (commercial) | Inoreader | Morning Brew (newsletter) | This System |
|---------|---------------------|-----------|---------------------------|-------------|
| Source management | Unlimited RSS, some HTML | RSS + web feeds | Curated by editors | User-registered RSS + HTML URLs |
| Filtering | AI-powered topics, tags | Rules, filters, keywords | Editorial selection | Per-source keyword matching |
| Summarization | AI summaries (paid tier) | None (full articles) | Human-written summaries | Claude AI one-line summaries |
| Delivery | Web app, mobile app | Web, mobile, email | Email newsletter | Telegram bot only |
| Language handling | Multi-language display | Multi-language | English only | Korean-unified summaries (any input language) |
| Configuration | Web UI | Web UI | None (subscribe/unsubscribe) | Telegram chat commands |
| Cost | $6-18/month per user | Free-$10/month | Free | Self-hosted (API costs only) |
| Target audience | Individual power users | Individual power users | General audience | Small team, niche industry |
| Customization | High (individual) | High (individual) | None | Moderate (shared team settings) |

**Key insight from competitor analysis:** Commercial aggregators optimize for individual users with broad interests and rich UIs. This system's niche is team-shared, domain-specific, AI-summarized briefings delivered to a chat interface -- a fundamentally different use case that commercial tools serve poorly.

## Sources

- SOP v2.1 (local document) -- primary requirements source
- PROJECT.md -- project context and constraints
- Domain knowledge of news aggregation systems (RSS, Atom, web scraping patterns)
- Domain knowledge of Telegram bot capabilities and limitations (4096 char message limit, polling vs webhook)
- Domain knowledge of Claude API capabilities for multilingual summarization
- Competitor analysis based on known feature sets of Feedly, Inoreader, and newsletter products

**Confidence note:** No web search was available during this research session. All findings are based on established domain knowledge and the detailed SOP document. The domain of news aggregation is well-established and unlikely to have shifted significantly. Confidence would be HIGH for table stakes and anti-features (stable domain patterns), MEDIUM for differentiators (could be missing recent innovations in AI-powered news tools).

---
*Feature research for: Automated news briefing system (IT/semiconductor/AI)*
*Researched: 2026-03-26*
