---
phase: 05-briefing-delivery-scheduling
plan: 02
subsystem: scheduling
tags: [jobqueue, telegram-bot, apscheduler, cron, kst-timezone]

requires:
  - phase: 05-01
    provides: "Telegram delivery functions (deliver_briefing, format_briefing_message, send_to_all_users)"
  - phase: 03
    provides: "Briefing pipeline (run_briefing_pipeline) for summarization"
  - phase: 02
    provides: "Collection engine (collect_all_sources) for article fetching"
  - phase: 01
    provides: "Database layer (get_setting, set_setting), main.py Application setup"
provides:
  - "JobQueue-based scheduler for KST-timed briefing delivery and interval collection"
  - "/set_times command for dynamic schedule changes without restart"
  - "/briefing command for immediate on-demand briefing"
  - "/collect command for immediate on-demand collection"
  - "Centralized setup_scheduled_jobs() called from main.py post_init"
affects: [06-production-deployment]

tech-stack:
  added: []
  patterns: ["JobQueue.run_daily for cron-like KST scheduling", "JobQueue.run_repeating for interval-based collection", "Lazy imports for circular dependency avoidance in scheduler callbacks"]

key-files:
  created:
    - src/services/__init__.py
    - src/services/scheduler.py
    - src/bot/delivery_handlers.py
  modified:
    - src/main.py

key-decisions:
  - "Replaced local job_collect/cmd_collect in main.py with centralized scheduler and delivery handler modules"
  - "Used lazy imports in job_briefing/job_collect to avoid circular dependencies between scheduler and pipeline/collector"

patterns-established:
  - "Services layer: src/services/ for cross-cutting job scheduling logic"
  - "Handler registration pattern: register_delivery_handlers(app) consistent with other handler modules"

requirements-completed: [DLV-01, DLV-02, DLV-03, DLV-04]

duration: 2min
completed: 2026-03-27
---

# Phase 5 Plan 2: Scheduled Delivery & Command Wiring Summary

**JobQueue-based KST briefing scheduler with /set_times, /briefing, /collect commands wired into main.py**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-27T01:03:43Z
- **Completed:** 2026-03-27T01:05:55Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- JobQueue scheduler service with run_daily for KST-timed briefings and run_repeating for collection intervals
- /set_times validates HH:MM input, saves to DB, and immediately updates JobQueue schedule without restart
- /briefing and /collect commands for on-demand briefing generation and article collection
- main.py refactored to use centralized scheduler and delivery handler modules

## Task Commits

Each task was committed atomically:

1. **Task 1: Create JobQueue scheduler service and delivery command handlers** - `226bcc6` (feat)
2. **Task 2: Wire scheduler and delivery handlers into main.py** - `3fe99da` (feat)

## Files Created/Modified
- `src/services/__init__.py` - Empty package init for services layer
- `src/services/scheduler.py` - JobQueue scheduler: job_briefing, job_collect, update_briefing_schedule, setup_scheduled_jobs
- `src/bot/delivery_handlers.py` - Command handlers: /set_times, /briefing, /collect with register_delivery_handlers
- `src/main.py` - Refactored to use centralized scheduler and delivery handler imports

## Decisions Made
- Replaced local job_collect/cmd_collect in main.py with imports from scheduler/delivery_handlers modules for single responsibility
- Used lazy imports inside job_briefing and job_collect callbacks to avoid circular dependency between scheduler and pipeline/collector modules

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all functions are fully wired to existing pipeline and collector modules.

## Next Phase Readiness
- Phase 5 complete: briefing delivery and scheduling fully integrated
- Ready for Phase 6 production deployment (systemd service, deploy.sh)

---
*Phase: 05-briefing-delivery-scheduling*
*Completed: 2026-03-27*
