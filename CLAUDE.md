Parallel Feature Development: Harness Racing Data Platform
Requirements Specification
1. System Overview
A full-stack harness racing data platform that scrapes, parses, normalizes, stores, and surfaces Australian harness racing results (harness.org.au) via a FastAPI backend and React frontend. Development is executed concurrently by 5 specialized implementer agents coordinated through /git-pr-workflows:git-workflow with mandatory pr-review-toolkit approval on every PR.

2. Team Composition (5 Parallel Implementers)
#Agent RolePrimary OwnershipBranch Prefix1Scraper EngineerPlaywright scraper, anti-bot subterfuge, meeting/results HTML acquisitionfeat/scraper/*2Parser/Transformer EngineerHTML parsing, dataclasses, time normalization (ss:ms), transformation pipelinefeat/parser/*3Database ArchitectSchema design, ERD, normalization, migrations, ORM modelsfeat/db/*4SQL-Pro / Backend EngineerFastAPI endpoints, query layer, par-times computation enginefeat/api/*5Frontend EngineerReact UI, data display, filters, race/meeting/par viewsfeat/web/*
Cross-cutting agents (always-on):

database-architect — invoked by Agent 3, produces ERD + ORM artefacts
sql-pro — invoked by Agent 4, owns retrieval queries + par-times SQL
pr-review-toolkit — MUST review/approve every PR before merge
debugger — auto-engaged on any logged ERROR/EXCEPTION


3. Repository & Workflow Requirements
3.1. A new GitHub repository named harness-racing-platform shall be initialized with:

main (protected, requires PR + pr-review-toolkit approval)
develop (integration branch)
Feature branches per agent following feat/<domain>/<ticket-id>-<slug>

3.2. /git-pr-workflows:git-workflow MUST be invoked for:

Branch creation
Commit signing/conventional commits (feat:, fix:, chore:, docs:)
PR opening with templated description, linked issue, test evidence
Merge (squash) only after pr-review-toolkit approval

3.3. Every PR must include:

Unit + integration tests (≥80% coverage on changed files)
Updated docs / ADR if architectural
Verbose log samples demonstrating success and failure paths
pr-review-toolkit sign-off comment

3.4. CI pipeline (GitHub Actions):

Lint (ruff, eslint), type-check (mypy, tsc), tests (pytest, vitest), build, security scan
All checks green required before pr-review-toolkit final approval

3.5. Parallel execution rules:

Agents 1–5 start concurrently from develop
Agent 3 (DB) publishes the v1 schema + ORM models within first sprint as an unblocking artefact
Agents 1, 2, 4 consume the ORM models via a shared packages/models module
Daily integration merge from develop into each feature branch


4. Feature Requirements
4.1 Scraper (Agent 1)
4.1.1 Form discovery & request generation

Parse the search form (month 1–12, year 1985–2026, state) and programmatically iterate every (month × year × state) tuple.
Construct the canonical results URL:
https://www.harness.org.au/racing/results/?month={m}&year={y}&state={s}&search_type=monthly
Headers and cookies from the supplied curl shall be templated; cookies rotated/regenerated per session.

4.1.2 Playwright with anti-blocking subterfuge

Use Playwright (async, Chromium) with playwright-stealth / equivalent patches.
Required evasions:

Randomised User-Agent pool (Firefox + Chrome desktop)
navigator.webdriver = false patch
Realistic viewport, locale (en-AU), timezone (Australia/Melbourne)
Plugins/WebGL/Canvas fingerprint spoofing
Human-like delays (gaussian jitter 800–2400ms) between navigations
Residential/rotating proxy support (config-driven)
Cookie jar persistence per session
Referer header chaining (previous month/state)
Retry with exponential backoff on 403/429/503 (max 5)
Captcha/blockpage detection → escalate to debugger agent, pause queue



4.1.3 Meeting list extraction

Locate <table class="meetingListFull"> and extract per <tr>:

Track name, meeting date, state, day/night, meeting URL (a href → ?mc=XXXXXXX)


Insert each unique track into raceTracks (idempotent upsert on track_name + state).
Insert each meeting row into raceMeetings with FK to raceTracks, status=PENDING_DOWNLOAD.

4.1.4 Meeting HTML download

Trigger condition: a complete year of meeting rows for a state has been ingested into raceMeetings.
For each pending meeting: meeting_url = base_url + href, fetch via Playwright with same subterfuge stack, store raw HTML to object/file store (raw_html/{state}/{year}/{meeting_code}.html), update raceMeetings.html_path + status=DOWNLOADED.

4.1.5 Concurrency & rate limits

Async worker pool (configurable, default 3) per state to avoid pattern detection.
Global token-bucket rate limiter (default 30 req/min).


4.2 Parser & Transformer (Agent 2)
4.2.1 Inputs

Reads raceMeetings rows where status=DOWNLOADED.
Loads raw HTML; parses meeting/race/runner data.

4.2.2 Parsing scope — build upon the supplied parse_results_html skeleton and extend to:

raceMoreInfo header: race_number, race_time, raceTitle (→ race_name), distance, raceInformation (→ race_purse, age_class, class, race_gait/start_type), final/interim flag.
raceFieldTable resultTable body: place, horse_id, horse_name, prizemoney→stake, barrier, tab#, trainer (+ link), driver (+ link), margin, starting_price, stewards comments (codes + tooltip full text).
raceTimes block: Track Rating, Gross Time, Mile Rate, Lead Time, four quarters, Margins (margin1, margin2).
Detect scratched runners and null_run, adjusted_margin, comment_adjustment.

4.2.3 Time normalization

All time fields (gross_time, lead_time, quarters, mile_rate, first_half, last_half) must be normalised to SS:ms (e.g., 2:07:1 → 127:100, 31.5 → 31:500).
Provide canonical numeric seconds (float) and display string.
Unit-tested conversion utility to_ss_ms(value: str | float) -> tuple[str, float].

4.2.4 Dataclasses (canonical model)
Implement Meeting, Race, Runner exactly per spec, with additions:

Race: race_name, race_distance, race_type, class_name, age_class, race_purse, start_type, race_gait, gross_time, lead_time, mile_rate, first_half, last_half, q1..q4, margin1, margin2, track_rating.
Runner: all fields per spec including finish_position, raw_margin, adjusted_margin, null_run, comment_codes, comment_adjustment, run_purse, raw_price.

4.2.5 Output

Transformer emits validated Pydantic models → ORM upsert into races, runners, race_times, stewards_comments.
Idempotency key: (meeting_code, race_number) and (meeting_code, race_number, horse_id).


4.3 Database (Agent 3 via database-architect)
4.3.1 Deliverables

Full ERD committed to /docs/erd/erd.png + /docs/erd/erd.dbml.
ORM models (SQLAlchemy 2.x, typed) in packages/models/.
Alembic migration baseline + per-feature migrations.
Seed scripts for tracks, states.

4.3.2 Normalisation

3NF minimum. Required core tables:

race_tracks (id, track_name, state, country, surface)
race_meetings (id, meeting_code UK, track_id FK, meeting_date, day_night, state, html_path, status, scraped_at)
races (id, meeting_id FK, race_number, race_name, distance_m, race_type, race_gait, start_type, class_name, age_class, race_purse, track_rating)
race_times (race_id FK, gross_time_ss_ms, lead_time_ss_ms, mile_rate_ss_ms, first_half, last_half, q1, q2, q3, q4, margin1, margin2)
horses (horse_id PK from source, horse_name, sex, foaled, sire_id, dam_id)
trainers, drivers (id, name, link_token UK)
runners (id, race_id FK, horse_id FK, runner_number, barrier, trainer_id FK, driver_id FK, finish_position, raw_margin, adjusted_margin, null_run, stake, raw_price, scratched)
stewards_comments (runner_id FK, codes, full_text, adjustment_value)
track_pars (track_id FK, distance_m, race_gait, start_type, condition, class, age_class, par_lead_time, par_gross_time, par_mile_rate, sample_size, computed_at)
scrape_log, parse_log, error_log (verbose logging tables)



4.3.3 Constraints & indexes

Unique: meeting_code, (meeting_id, race_number), (race_id, horse_id).
Indexes on meeting_date, track_id, state, horse_id, (track_id, distance_m, race_gait, start_type).
All _ss_ms columns stored as INTERVAL or NUMERIC(8,3) seconds with computed display column.


4.4 Backend API & SQL (Agent 4 via sql-pro)
4.4.1 FastAPI middleware

Endpoints (all paginated, OpenAPI documented):

GET /meetings?state&year&month
GET /meetings/{meeting_code}
GET /races/{race_id} (full race + runners + times)
GET /horses/{horse_id}/form
GET /trainers/{id}, GET /drivers/{id}
GET /tracks/{id}/pars?distance&gait&start_type&condition&class&age_class
GET /search?q=


Auth: API key for write/admin; public read with rate-limit.
Response models: Pydantic; ETag + cache headers.

4.4.2 SQL deliverables (sql-pro)

Hand-written, EXPLAIN-verified queries for all endpoints in /sql/queries/.
Materialised view mv_par_times refreshed nightly.

4.4.3 Par-times computation engine

Input signature mirrors spec:
Copytrack_pars(
  track_name, distance, condition="Good",
  class, age_class, race_purse,
  start_type, race_gait,
  par_lead_time, par_gross_time, par_mile_rate
)

Algorithm:

Group historical races by (track_id, distance_m, race_gait, start_type, condition, class, age_class).
Compute trimmed mean (10/90 percentile trim) of lead_time, gross_time, mile_rate in seconds.
Output in ss:ms and float seconds.
Persist to track_pars with sample_size and computed_at.


Exposed via /tracks/{id}/pars and used to enrich /races/{race_id} responses (delta vs par).


4.5 Frontend (Agent 5)
4.5.1 Stack

React 18 + TypeScript + Vite, TanStack Query, React Router, Tailwind, shadcn/ui.

4.5.2 Views

Meetings calendar (filter by state/year/month)
Meeting detail (race list)
Race detail (runners table, times, par deltas highlighted)
Horse / Driver / Trainer profile pages with form lines
Track par-times explorer (filter by distance, gait, condition, class)

4.5.3 UX

Times displayed in canonical ss:ms.
Par deltas colour-coded (green faster, red slower).
Loading skeletons, error boundaries, offline cache via TanStack Query.


5. Logging, Error Handling & Debugger Engagement
5.1. Verbose logging is mandatory at every stage:

Python: structlog JSON to stdout + rotating file + error_log DB table.
Levels: DEBUG (per-request, per-row), INFO (lifecycle), WARNING (retries, soft parse failures), ERROR (exceptions, blockpages), CRITICAL (pipeline halt).
Every log entry: timestamp, agent, module, action, meeting_code?, race_number?, horse_id?, attempt, latency_ms, outcome, payload_hash.

5.2. Auto-debugger trigger:

Any ERROR/CRITICAL log row OR test failure shall invoke the debugger agent with the log context, stack trace, last successful checkpoint, and offending HTML snippet.
Debugger must produce a fix PR (fix/debug/<error-id>) routed through /git-pr-workflows:git-workflow and pr-review-toolkit.

5.3. Exception policy:

No silent excepts. All except clauses log + re-raise or enqueue to dead-letter table parse_dlq / scrape_dlq.
DLQ items reprocessed after debugger fix is merged.


6. Acceptance Criteria

✅ New GitHub repo bootstrapped; all 5 agents have at least one merged PR via /git-pr-workflows:git-workflow + pr-review-toolkit approval.
✅ Scraper can enumerate every (month, year, state) and ingest meetings for VIC 1985–2026 without being blocked (≥99% success).
✅ All race times stored and rendered as ss:ms.
✅ ERD + ORM models published; migrations apply cleanly to empty DB.
✅ /tracks/{id}/pars returns computed pars for any valid filter combination.
✅ React UI renders a race page end-to-end from live DB.
✅ 100% of errors visible in error_log table and triaged by debugger agent.
✅ Zero PRs merged without pr-review-toolkit approval comment.
Add to Conversation