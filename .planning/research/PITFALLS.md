# Pitfalls Research

**Domain:** Python-based news aggregation with Telegram bot delivery and LLM summarization
**Researched:** 2026-03-26
**Confidence:** MEDIUM (training data only -- web search unavailable for verification)

## Critical Pitfalls

### Pitfall 1: python-telegram-bot run_polling() owns the event loop

**What goes wrong:**
`Application.run_polling()` calls `asyncio.run()` internally, which creates and owns the event loop. If you try to run APScheduler's `AsyncIOScheduler` alongside it, you hit one of two problems: (a) you cannot call `asyncio.run()` twice, or (b) the scheduler starts on a different loop than the bot. The result is either a crash on startup or silently dead scheduled jobs.

**Why it happens:**
Developers treat the Telegram bot and the scheduler as two independent services and try to start them separately. The `run_polling()` convenience method hides that it takes over the entire process event loop.

**How to avoid:**
Do NOT use `run_polling()`. Instead, use the lower-level `Application.initialize()` / `Application.start()` / `Application.updater.start_polling()` pattern, which lets you control the event loop yourself. Create one `asyncio` event loop, start the scheduler on it, start the bot updater on it, then `loop.run_forever()`. Alternatively, use `python-telegram-bot`'s built-in `JobQueue` (which wraps APScheduler internally) instead of running a separate APScheduler instance -- this is the cleanest solution for this project.

**Warning signs:**
- Scheduled jobs never fire but bot commands work fine
- "This event loop is already running" errors at startup
- Jobs fire once then stop after bot reconnects

**Phase to address:**
Phase 1 (foundation) -- this is an architectural decision that must be correct from the start. Changing the concurrency model later requires rewriting the main entry point and all job registration code.

---

### Pitfall 2: HTML parsing breaks silently when sites change layout

**What goes wrong:**
A "generic" HTML parser that extracts article links and content from news sites works initially, then silently starts returning empty results or garbage when a site redesigns. The system keeps running, the scheduler fires, but briefings contain 0 articles from that source -- and nobody notices for days.

**Why it happens:**
News sites change HTML structure frequently (A/B tests, redesigns, ad framework changes). A generic parser using CSS selectors or tag heuristics has no contract with the source site. Unlike RSS (which is a stable contract), HTML parsing is inherently fragile.

**How to avoid:**
1. **Per-source health monitoring:** Track articles-found-per-source over time. Alert (via Telegram) when a source drops to 0 articles for 2+ consecutive fetches.
2. **Two-tier parser strategy:** Use RSS (feedparser) for Tier 1 sources. For HTML-only sources, build a `BaseParser` with per-site subclasses so when one breaks, the fix is scoped to one file.
3. **Store raw HTML snapshots** for the last successful parse per source, so you can diff when debugging a broken parser.
4. **Fallback heuristics:** For article content extraction, use `readability-lxml` or `newspaper3k` as a fallback -- these use statistical methods rather than CSS selectors.

**Warning signs:**
- A source suddenly returns 0 articles when it previously returned 5-10
- Article titles come back as navigation menu items or ad text
- Content extraction returns boilerplate (cookie notices, footer text)

**Phase to address:**
Phase 2 (collection engine) -- build monitoring from the start. The generic parser MVP is fine, but it MUST include zero-article detection.

---

### Pitfall 3: Claude API costs spiral from naive per-article summarization

**What goes wrong:**
Sending each article to Claude individually for summarization results in high API costs and rate limit hits. With 13 sources and potentially 50-100 articles per briefing cycle, individual requests mean 50-100 API calls per briefing. At ~$3/M input tokens for Sonnet, costs seem low per-call but add up, and rate limits (especially requests-per-minute) become the real bottleneck.

**Why it happens:**
The natural mental model is "one article = one summary." Developers don't batch because each article seems like an independent unit.

**How to avoid:**
1. **Batch articles into a single prompt.** Send all filtered articles for one briefing as a single prompt: "Summarize each of these N articles in one line, format: [keyword] summary (source)." This cuts API calls from N to 1 per briefing cycle.
2. **Filter BEFORE summarization.** Apply keyword filtering on titles/content locally first. Only send matched articles to Claude. This is the biggest cost saver.
3. **Set a token budget.** Truncate article content to ~500-1000 chars each before sending. Headlines + first paragraphs carry 90% of the information for a one-line summary.
4. **Cache summaries.** Use the article URL as a dedup key. Never re-summarize the same article.

**Warning signs:**
- Monthly Anthropic bill exceeds $10 for a small-team news briefing
- "Rate limit exceeded" errors during briefing generation
- Briefing generation takes >60 seconds

**Phase to address:**
Phase 3 (summarization) -- design the batching strategy before writing the first API call.

---

### Pitfall 4: SQLite "database is locked" under concurrent scheduler + bot access

**What goes wrong:**
APScheduler job fires a collection task that writes articles to SQLite. Simultaneously, a user sends a Telegram command that reads from the same database. SQLite's default journal mode uses file-level locking -- the read blocks or the write fails with "database is locked" after the default 5-second timeout.

**Why it happens:**
SQLite handles concurrency poorly in its default (DELETE) journal mode. Developers assume "it's just a small database" and skip concurrency configuration. The problem is intermittent -- it only occurs when a scheduled job and a bot command overlap, which is rare but inevitable.

**How to avoid:**
1. **Enable WAL mode on first connection:** `PRAGMA journal_mode=WAL;` -- this allows concurrent reads during writes.
2. **Set a busy timeout:** `PRAGMA busy_timeout=5000;` so writers retry instead of failing immediately.
3. **Use a single connection with serialized access** or use `aiosqlite` with a connection pool of 1 writer + N readers.
4. **Never hold transactions open during I/O.** Fetch articles, close the HTTP connection, THEN write to DB in a single fast transaction.

**Warning signs:**
- Occasional "database is locked" errors in logs
- Bot commands timeout sporadically
- Missing articles that were collected but never persisted

**Phase to address:**
Phase 1 (foundation) -- WAL mode and busy_timeout must be set in the database initialization code from day one.

---

### Pitfall 5: feedparser silently accepts broken/empty feeds

**What goes wrong:**
`feedparser.parse()` almost never raises exceptions. It returns a result object even for HTTP 404, connection timeouts, invalid XML, or empty feeds. The `bozo` flag indicates parse errors but the entries list may still be partially populated with garbage. Developers check `len(feed.entries) > 0` and assume success.

**Why it happens:**
feedparser was designed to be maximally tolerant of broken RSS/Atom feeds. This is a feature for browsers but a trap for automated systems that need to distinguish "no new articles" from "feed is broken."

**How to avoid:**
1. **Check `feed.bozo` AND `feed.status`** (HTTP status code). A 200 status + `bozo=False` + entries = reliable. A 404 or `bozo=True` with 0 entries = broken feed, alert the user.
2. **Track last-successful-fetch timestamp per source.** If a source hasn't returned articles in 24+ hours, flag it.
3. **Validate entry structure.** Check that each entry has at minimum `title` and `link` before processing.
4. **Handle `feed.status` missing** -- feedparser doesn't set it for local file parsing or certain error conditions.

**Warning signs:**
- Source shows 0 articles consistently but you know articles were published
- `bozo_exception` is `SAXParseException` (XML changed) or `URLError` (site down)
- Entries have titles but links are `None`

**Phase to address:**
Phase 2 (collection engine) -- build feed validation into the RSS collector from the start.

---

### Pitfall 6: Telegram message length limit truncates briefings

**What goes wrong:**
Telegram messages have a 4096-character limit (with Markdown/HTML formatting). A briefing with 20+ articles easily exceeds this. The `python-telegram-bot` library raises `BadRequest: Message is too long` and the entire briefing fails to send.

**Why it happens:**
Developers test with 3-5 articles and never hit the limit. In production, a busy news day produces 30+ matches.

**How to avoid:**
1. **Split messages proactively.** Calculate message length before sending. If >4000 chars, split into multiple messages with "[1/3]" headers.
2. **Use MarkdownV2 carefully.** MarkdownV2 requires escaping many special characters (`.`, `-`, `(`, `)`, etc.). Unescaped characters cause `BadRequest: Can't parse entities`. Use HTML parse_mode instead -- it's more predictable.
3. **Implement a `send_long_message()` helper** from day one that handles splitting.

**Warning signs:**
- Briefings work in testing but fail in production on busy news days
- `BadRequest` exceptions in logs
- Users receive partial briefings

**Phase to address:**
Phase 4 (Telegram delivery) -- but design the message formatting layer with splitting in mind from the summarization phase.

---

### Pitfall 7: systemd service dies silently on unhandled async exceptions

**What goes wrong:**
An unhandled exception in an async callback (scheduler job, telegram handler) kills the asyncio task but not the process. The systemd service shows "active (running)" but the bot is dead -- no scheduled jobs fire, no commands respond. Or conversely, an unhandled exception kills the process, systemd restarts it, but the restart loop happens so fast that systemd gives up ("start request repeated too quickly").

**Why it happens:**
asyncio swallows exceptions in tasks by default (logs them but doesn't crash the process). Developers assume systemd's `Restart=always` is sufficient, but it doesn't help if the process is alive but functionally dead.

**How to avoid:**
1. **Global exception handler for asyncio:** Set `loop.set_exception_handler()` to log AND trigger a health alert via Telegram (to a separate admin chat or the same bot).
2. **Health check endpoint or heartbeat.** Write a timestamp to a file every scheduler tick. Use a separate systemd timer or watchdog to check staleness.
3. **systemd WatchdogSec:** Configure `WatchdogSec=300` and call `sd_notify("WATCHDOG=1")` from your health check. systemd kills the process if the watchdog isn't refreshed.
4. **RestartSec=10** in the service file to prevent restart-loop throttling.
5. **Wrap every handler in try/except** that logs to file, not just stderr.

**Warning signs:**
- Service status shows "active" but no briefings arrive
- Log file stops being written to
- Users report "bot is not responding" but systemd says it's running

**Phase to address:**
Phase 5 (deployment) -- but error handling patterns must be established in Phase 1 foundation code.

---

### Pitfall 8: Korean/English mixed content breaks keyword matching

**What goes wrong:**
Keyword filtering on Korean news sites fails because: (a) Korean has no word boundaries (spaces separate phrases, not words), (b) the same concept appears in Korean ("반도체") and English ("semiconductor") across different sources, (c) site encodings vary (UTF-8 vs EUC-KR on older Korean sites), causing mojibake that breaks all matching.

**Why it happens:**
Developers test with English sources, then add Korean sources and assume the same string-matching approach works.

**How to avoid:**
1. **Force UTF-8 everywhere.** On HTTP fetch, detect encoding with `chardet` or `charset-normalizer` and decode to UTF-8 before any processing. feedparser handles this automatically for RSS; BeautifulSoup needs explicit `from_encoding` for some Korean sites.
2. **Keyword matching: case-insensitive for English, exact match for Korean.** Use `keyword.lower() in text.lower()` for English, plain `keyword in text` for Korean. Store keywords with a language hint.
3. **Support keyword synonyms/aliases.** Allow "semiconductor|반도체" as a single logical keyword. Filter matches if EITHER variant appears.
4. **Normalize whitespace and HTML entities** before matching. Korean sites sometimes use `&nbsp;` between characters.

**Warning signs:**
- Korean sources match 0 articles despite obvious keyword presence on the site
- Garbled characters in article titles in the database
- Same keyword catches articles from English sources but not Korean ones

**Phase to address:**
Phase 2 (collection engine) -- encoding handling must be correct in the fetcher, and keyword matching logic must support bilingual content.

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoded CSS selectors per site | Fast parser for MVP | Every site redesign = code change | MVP only -- refactor to config-driven parsers in Phase 2 |
| Single SQLite connection shared across threads | Simple setup | Locked DB errors under load | Never -- use WAL mode from day one |
| No article content truncation before Claude API | Full context for summarization | 10x higher API costs | Never -- truncate to first 500-1000 chars |
| String concatenation for Telegram messages | Quick to implement | Breaks on special characters, length limits | Never -- use a message builder from the start |
| Storing API keys in code | Fast prototyping | Security breach, cannot rotate | Never -- use .env files from day one |
| No retry logic on HTTP fetches | Simpler code | Transient failures cause missed articles | MVP only -- add exponential backoff in Phase 2 |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Anthropic Claude API | Not handling 429 (rate limit) or 529 (overloaded) responses | Implement exponential backoff with jitter. The `anthropic` Python client has built-in retries -- enable them with `max_retries=3` |
| Telegram Bot API | Using Markdown parse_mode (v1) which silently drops formatting | Use `parse_mode=ParseMode.HTML` -- more predictable escaping, fewer edge cases |
| Telegram Bot API | Not handling `Flood control exceeded` (429) on bulk sends | Add 0.5s delay between messages when sending to multiple users. Telegram rate limits per-chat |
| feedparser | Assuming `feed.entries[0].published_parsed` always exists | Many feeds omit `published`. Fall back to `updated`, then to current timestamp |
| BeautifulSoup4 | Using `html.parser` (stdlib) which fails on malformed HTML | Use `lxml` parser -- faster and more tolerant of broken HTML from news sites |
| SQLite via aiosqlite | Forgetting that aiosqlite wraps sync sqlite3 in a thread -- it's not truly async | Acceptable for this scale. Keep transactions short. Don't hold connections across await points |
| requests/httpx | Not setting a timeout, causing the entire scheduler to hang on a dead site | Always set `timeout=30` (or use httpx which has better timeout granularity) |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fetching all sources sequentially | Briefing generation takes 5+ minutes | Use `asyncio.gather()` to fetch sources concurrently (limit to 5 concurrent with semaphore) | >10 sources |
| Re-parsing entire feed instead of checking new entries only | Unnecessary CPU and bandwidth | Track `ETag`/`Last-Modified` headers; feedparser supports `etag` and `modified` params | >20 sources fetched hourly |
| Loading all articles into memory for dedup | Memory growth over months | Dedup against DB with indexed URL column, not in-memory set | >10K articles in DB |
| Sending full article HTML to Claude | Slow responses, high token cost | Extract and truncate plain text before API call | >20 articles per briefing |
| No DB cleanup/archival | SQLite file grows unbounded | Add a cleanup job: archive or delete articles older than 30 days | >100K rows (~6 months) |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Telegram bot token in source code or git | Token theft, bot hijacking | Store in `.env`, add `.env` to `.gitignore`, use `python-dotenv` |
| Anthropic API key in source code | Unauthorized API usage, billing | Same as above -- `.env` file, never committed |
| No chat_id validation on bot commands | Anyone who discovers the bot can change settings | Maintain an allow-list of authorized `chat_id`s. Reject commands from unknown users |
| Following redirects blindly during scraping | SSRF -- scraper could be directed to internal GCP metadata endpoints (169.254.169.254) | Validate URLs against an allow-list of registered domains. Block private IP ranges |
| Running bot as root on GCP | Full server compromise if bot is exploited | Create a dedicated `newsbot` user with minimal permissions. Run systemd service as that user |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Sending all briefing articles in one wall of text | Overwhelming, hard to scan | Group by source or topic. Use clear section headers. Split into multiple messages if needed |
| No confirmation after bot commands | User unsure if command worked | Always reply with current state after changes: "Keyword 'AI' added. Current keywords: [AI, 반도체, DRAM]" |
| No way to see current configuration | User forgets what sources/keywords are active | `/status` command showing all sources, keywords, schedule, and last briefing time |
| Briefing arrives but contains 0 articles | User thinks system is broken | Send "No matching articles found since last briefing" instead of silence |
| Error messages in English for Korean-speaking team | Confusion | All bot responses in Korean since the team operates in Korean |

## "Looks Done But Isn't" Checklist

- [ ] **RSS Collection:** Often missing ETag/Last-Modified caching -- verify conditional GET requests work
- [ ] **HTML Parsing:** Often missing encoding detection -- verify Korean sites render correctly in DB
- [ ] **Keyword Filtering:** Often missing bilingual matching -- verify "반도체" matches Korean sites AND "semiconductor" matches English sites for the same logical keyword
- [ ] **Summarization:** Often missing token counting -- verify input doesn't exceed Claude's context window (even batched)
- [ ] **Telegram Delivery:** Often missing message splitting -- verify briefings with 30+ articles deliver correctly
- [ ] **Telegram Delivery:** Often missing special character escaping -- verify article titles with `()[]_*` chars don't break formatting
- [ ] **Deduplication:** Often missing URL normalization -- verify `http` vs `https`, trailing slashes, query params don't cause duplicate articles
- [ ] **Scheduling:** Often missing timezone handling -- verify schedule times are KST (Asia/Seoul), not UTC
- [ ] **systemd Service:** Often missing proper shutdown -- verify SIGTERM triggers graceful cleanup (flush DB, close connections)
- [ ] **Logging:** Often missing structured logging -- verify you can grep logs by source, by phase (fetch/filter/summarize/deliver)

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Event loop conflict (bot + scheduler) | MEDIUM | Rewrite main.py entry point to use manual loop management or switch to built-in JobQueue |
| Broken HTML parser for a source | LOW | Disable source via bot command, fix parser, redeploy. No data loss |
| Claude API cost overrun | LOW | Switch to batched prompts immediately. Review and truncate article content. Set billing alerts |
| SQLite locked errors | LOW | Enable WAL mode (one-line fix). If data corrupted, restore from last good backup |
| Silent service death | MEDIUM | Add watchdog + health check. Review logs to find the root exception. Add try/except to all handlers |
| Encoding issues (mojibake) | MEDIUM | Re-fetch affected articles with correct encoding. Add charset-normalizer to fetch pipeline |
| Telegram flood control | LOW | Add per-user send delay. If bot is temporarily restricted, wait 30 minutes (Telegram auto-unblocks) |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Event loop conflict | Phase 1 (Foundation) | Bot starts AND scheduled jobs fire in the same process |
| SQLite locking | Phase 1 (Foundation) | WAL mode enabled; concurrent read during write succeeds |
| HTML parsing fragility | Phase 2 (Collection) | Zero-article alert fires when a source returns nothing |
| feedparser silent failures | Phase 2 (Collection) | Broken feed URL produces a warning, not silent empty results |
| Encoding/bilingual issues | Phase 2 (Collection) | Korean article titles stored correctly in DB; bilingual keyword match works |
| API cost/rate limits | Phase 3 (Summarization) | Batched prompt used; cost per briefing logged and < $0.05 |
| Message length/formatting | Phase 4 (Delivery) | 30+ article briefing sends successfully as split messages |
| Chat ID authorization | Phase 4 (Delivery) | Unknown chat_id receives rejection message |
| Silent service death | Phase 5 (Deployment) | Watchdog kills and restarts process within 5 minutes of hang |
| Timezone misconfiguration | Phase 5 (Deployment) | Briefing arrives at configured KST time, not UTC equivalent |

## Sources

- Training data knowledge of python-telegram-bot v20+ architecture (Application class, JobQueue)
- Training data knowledge of APScheduler v3.x event loop behavior
- Training data knowledge of SQLite concurrency model (WAL mode, busy_timeout)
- Training data knowledge of feedparser bozo flag behavior
- Training data knowledge of Telegram Bot API message limits and flood control
- Training data knowledge of Anthropic Python client retry behavior

**NOTE:** Web search and documentation fetch were unavailable during this research. All findings are based on training data (cutoff ~May 2025). Confidence is MEDIUM -- these are mature, well-documented libraries with well-known pitfalls, but specific version details should be verified against current docs during implementation.

---
*Pitfalls research for: Python news aggregation + Telegram bot briefing system*
*Researched: 2026-03-26*
