# Sprint 1 Decomposition Plan

Builds on `docs/decomposition-plan.md` (Sprint 0 horizontal-layer split). The 5 lanes stay; the per-lane scope expands from stubs to production-grade implementations.

## Goal

End of Sprint 1 demonstrates the full data path **end-to-end for one state, one month**:

```
Playwright (anti-bot) → meeting list ingest → meeting HTML download
  → parser (full §4.2) → ORM upsert
  → API endpoints (full §4.4) + par-times engine
  → React (real TS client, real views)
```

Acceptance gate: a user opens the web UI, picks `VIC / January 2024`, and sees the actual meetings, races, runners, and par-time deltas pulled from `harness.org.au` via the real pipeline.

## Open decisions — resolve BEFORE Sprint 1 spawn

These cannot be defaulted; agents need answers.

| # | Decision | Default if not chosen | Recommended |
|---|----------|----------------------|-------------|
| D1 | **Proxy provider** for scraper (CLAUDE.md §4.1.2) | None (dev only, will likely get blocked at scale) | BrightData residential or ScrapeOps; or "none, accept block risk for Sprint 1" |
| D2 | **Scraper orchestration** runtime | Standalone `async` CLI (simplest, no infra) | Temporal (durable, retries built-in) if production-bound; else stay with CLI |
| D3 | **Par-times trim percentiles** (§4.4.3) | 10/90 per spec | Confirm 10/90 vs alternative like 25/75 for tight populations |
| D4 | **Auth secrets storage** | `.env` only | OK for dev; defer KMS to Sprint 2 |
| D5 | **Hosting target** | Compose-only (dev) | Render / Fly.io / AWS — drives Dockerfile + IaC scope |
| D6 | **Scraper fixture HTML** | None | Save 3-5 real meeting HTMLs to `tests/fixtures/` so parser can develop offline |
| D7 | **PR review automation** — does pr-review-toolkit auto-comment, or is each agent run manually? | Manual per PR | Manual unless you wire a GH Action; spec mandates the gate but doesn't say how |

## Lane scope

### Agent 3 (DB) — small + foundational, runs first

Branch: `feat/db/sprint-1-pars-and-seeds`

Deliverables:
- `mv_par_times` materialised view DDL (Alembic migration `0002_par_times_view.py`). Grouping keys per §4.4.3: `(track_id, distance_m, race_gait, start_type, condition, class_name, age_class)`. Window over `races + race_times` with trimmed-mean aggregates.
- Refresh helper: `harness_models.pars.refresh_par_times(session)` calling `REFRESH MATERIALIZED VIEW CONCURRENTLY mv_par_times`.
- Generated/computed display columns for every `*_ss_ms` field (concat helper expression). Adds `gross_time_display`, `lead_time_display`, etc. — `STORED GENERATED` per Postgres 16.
- Seed scripts: `packages/models/seeds/tracks.csv` + state list + loader command `python -m harness_models.seed`.
- Indexes per §4.3.3 verified by `EXPLAIN`.

Risk: trimmed-mean SQL is non-trivial. Use `PERCENTILE_CONT(0.1) WITHIN GROUP` + `PERCENTILE_CONT(0.9)` + `AVG()` filtered to the inter-percentile range. Test with synthetic data in `test_par_times.py`.

### Agent 1 (Scraper) — heaviest backend work

Branch: `feat/scraper/sprint-1-subterfuge-and-ingest`

Phase 1A — anti-bot suite (CLAUDE.md §4.1.2):
- UA pool (Firefox-desktop + Chrome-desktop, rotated per session)
- `playwright-stealth` plugin OR explicit patches: `navigator.webdriver = false`, plugins/WebGL/canvas fingerprint spoofing
- Viewport randomisation, locale `en-AU`, timezone `Australia/Melbourne`
- Gaussian jitter delays (800–2400ms) between navigations
- Cookie jar persistence per session (file-backed)
- Referer header chaining
- Proxy support: read `SCRAPER_PROXY_URL`; if set, route through it
- Token-bucket rate limiter (30 req/min global)
- Async worker pool (3/state)
- Exponential backoff retry via `tenacity` on 403/429/503 (max 5)
- Captcha/blockpage detector → raises typed exception, logs ERROR (debugger auto-engages per §5.2)

Phase 1B — meeting list ingest (§4.1.3):
- `extract_meetings(html: str) -> list[MeetingRow]` parses `table.meetingListFull`
- Idempotent upsert into `race_tracks` (track_name + state UK) and `race_meetings` (meeting_code UK)
- Status transitions: `PENDING_DOWNLOAD` on insert

Phase 1C — meeting HTML download (§4.1.4):
- Trigger: complete-year-per-state ingest (use a `scrape_progress` view; coordinate with Agent 3)
- For each `PENDING_DOWNLOAD` meeting, fetch `?mc=XXXXXXX`, save to `raw_html/{state}/{year}/{meeting_code}.html`, update `html_path` + status to `DOWNLOADED`

Phase 1D — fixture export:
- Save 5 representative HTMLs to `tests/fixtures/meetings/` for Parser's use (see D6)

Concurrency: per-state async worker pool ≤ 3 with shared rate limiter. Real-site integration test marked `@pytest.mark.network` (CI opt-in).

Risk: captcha. Mitigation: residential proxy via D1 OR accept block risk for Sprint 1 with a debugger queue.

### Agent 2 (Parser) — heaviest data-layer work

Branch: `feat/parser/sprint-1-full-pipeline`

Deliverables:
- Complete `parse_results_html(html: str) -> MeetingDTO` per §4.2.2:
  - `raceMoreInfo` header → race_number, race_time, race_name, distance, race_purse, age_class, class, race_gait/start_type, final/interim flag
  - `raceFieldTable.resultTable` → place, horse_id, horse_name, prizemoney→stake, barrier, tab#, trainer+link, driver+link, margin, starting_price, stewards (codes + tooltip text)
  - `raceTimes` → Track Rating, Gross Time, Mile Rate, Lead Time, Q1-Q4, Margin1, Margin2
- Scratched-runner detection, `null_run`, `adjusted_margin`, `comment_adjustment` extraction
- `to_ss_ms` applied to every time column (parser pulls from `harness_models.time_utils` Protocol — now available)
- `transformer.upsert_meeting(session, meeting_dto)` writes through ORM with idempotency:
  - `(meeting_code, race_number)` for races
  - `(meeting_code, race_number, horse_id)` for runners
- DLQ: parse errors enqueue to `parse_dlq` (Agent 3 must add this table — coordinate)
- Structlog at every stage per §5.1

Tests: fixture-driven (D6 dependency on Agent 1's Phase 1D). Aim for 90%+ coverage on `parse.py`; 100% on `transformer.py`.

### Agent 4 (Backend / sql-pro) — heaviest API work

Branch: `feat/api/sprint-1-endpoints-and-pars`

All endpoints (§4.4.1), each with hand-written EXPLAIN-verified SQL in `sql/queries/`:

| Endpoint | SQL file |
|----------|----------|
| `GET /meetings?state&year&month` | `meetings_list.sql` (already exists; extend) |
| `GET /meetings/{meeting_code}` | `meeting_detail.sql` |
| `GET /races/{race_id}` | `race_detail.sql` (join runners + times + par delta) |
| `GET /horses/{horse_id}/form` | `horse_form.sql` |
| `GET /trainers/{id}` | `trainer_detail.sql` |
| `GET /drivers/{id}` | `driver_detail.sql` |
| `GET /tracks/{id}/pars?distance&gait&start_type&condition&class&age_class` | `track_pars.sql` (against `mv_par_times`) |
| `GET /search?q=` | `search.sql` (Postgres full-text index on horse/track/trainer/driver names) |

Par-times computation engine (§4.4.3):
- `services/api/src/api/pars.py`: `compute_par(session, filters) -> ParTimes`
- Reads from `mv_par_times` (Agent 3); falls back to live aggregation if mv stale > 24h
- `POST /admin/refresh-pars` (API-key gated) triggers `refresh_par_times`

Auth:
- API-key dependency on write/admin endpoints (`/admin/*`)
- Public read with per-IP rate-limit (slowapi)

Cross-cutting:
- ETag + `Cache-Control: public, max-age=60` for read endpoints
- All endpoints paginated (`limit` ≤ 100, `offset` ≥ 0)
- Pydantic v2 response models exported via OpenAPI

Tests: TestClient against a postgres testcontainer with seed fixtures; coverage ≥ 80%.

### Agent 5 (Web) — heaviest frontend work

Branch: `feat/web/sprint-1-views-and-client`

Deliverables:
- Generate TS client from `apps/web/openapi.json` (committed by Agent 4) via `openapi-typescript` → `apps/web/src/api/types.ts`
- TanStack Query hook layer in `apps/web/src/api/queries.ts` — one `use<Endpoint>` per route, with retry + offline cache (§4.5.3)
- Real shadcn/ui init (Button, Input, Select, Sheet, Dialog, Tooltip, Dropdown, Skeleton, Toast)
- Views (§4.5.2):
  - Meetings calendar (state/year/month filters)
  - Meeting detail (race list with quick-glance time + winner)
  - Race detail (runners table + times + colour-coded par deltas)
  - Horse / Driver / Trainer profile pages with form lines
  - Track par-times explorer (filter by distance, gait, condition, class, age)
- Error boundaries per route
- Loading skeletons for every async section
- 404 + 500 fallbacks
- E2E test: Playwright run that loads RacePage from a mocked API and asserts par delta colour

Risk: openapi-typescript fails if Agent 4's OpenAPI shape changes mid-sprint. Mitigation: pin to a snapshot version at sprint start and bump only via broadcast.

## Cross-lane contracts (changes from Sprint 0)

These are the **only** mutations to shared surfaces during Sprint 1. Each requires a broadcast (file an issue tagged `contract-change`).

| Contract file | Change | Owner |
|---------------|--------|-------|
| `packages/models/__init__.py` | Add `MvParTime`, `ParseDlq`, `ScrapeDlq` exports | Agent 3 |
| `packages/models/seeds/` | New directory, seed CSVs + loader | Agent 3 |
| `tests/fixtures/meetings/` | New directory, 5 real meeting HTMLs | Agent 1 (cross-lane: Agent 2 reads) |
| `apps/web/openapi.json` | Committed snapshot from Agent 4 | Agent 4 (Agent 5 reads) |
| `sql/queries/*.sql` | 7 new query files | Agent 4 |
| `sql/migrations/0002_par_times_view.py` | New migration | Agent 3 |

## Integration order

```
Day 0:  Sprint 0 PRs merged to develop (squash; pr-review-toolkit gate)
        Open decisions D1–D7 resolved
Day 1:  Agent 3 lands mv_par_times + seeds (small) — first PR merged
        Other 4 agents start in parallel from updated develop
Day 5:  Agent 1 Phase 1D fixture HTMLs committed — unblocks Agent 2
        Agent 4 commits OpenAPI snapshot — unblocks Agent 5 client gen
Day 10: PR review for Agent 1, 2, 4 (in any order; data + API independent)
Day 12: Agent 5 PR — depends on Agent 4 merged
Day 14: Integration smoke test on develop; user acceptance test of e2e path
```

## Risks + debugger triggers

| Risk | Likelihood | Trigger condition | Owner |
|------|-----------|-------------------|-------|
| harness.org.au blocks scraper | High without proxy (D1) | HTTP 403/429 OR captcha selector seen → ERROR log | debugger auto-engages per §5.2 |
| Stewards-comment tooltip parsing brittle (regex on inline JS / data-attrs) | Medium | parse_dlq grows | debugger + Agent 2 |
| `mv_par_times` slow to refresh on full dataset | Medium | refresh time > 5min in CI | Agent 3 + sql-pro |
| OpenAPI drift between API and Web | Medium | typecheck fails on Web after API merge | broadcast + re-gen client |
| Playwright Chromium download too large for CI | Low | CI runtime > 20min | use `playwright install --with-deps chromium` cache |

## Sprint 1 NOT-doing

Defer to Sprint 2+:
- Historical backfill of 1985–2026 (Sprint 1 = VIC + January 2024 only)
- KMS / secrets manager (use .env)
- Production deployment / IaC (compose-only stays)
- Multi-region/edge caching
- WebSockets / live results
- Authentication beyond API key (no users/sessions yet)
- Mobile responsive polish (basic Tailwind defaults only)
- Search analytics, click-tracking
- Admin UI

## Decomposition strategy recap

Per `agent-teams:parallel-feature-development` skill: **hybrid horizontal-layer split** continues. The single shared contract (`packages/models`) stays sole-owner Agent 3. Sprint 1 adds two new cross-lane contracts (fixture HTMLs + OpenAPI snapshot), both single-owner with read-only consumers. No file is owned by two agents.

The "Implementers blocking each other waiting for shared code" risk from the skill troubleshooting list is mitigated by the staging-interface pattern: Agent 1 publishes fixture HTMLs early so Agent 2 doesn't wait for the full scraper; Agent 4 publishes the OpenAPI snapshot early so Agent 5 can typecheck against it before all endpoints are done.

## Operational lesson from Sprint 0 — worktree isolation

Sprint 0 used `Agent({isolation: "worktree"})` for all 5 implementers. On Windows, this did NOT create separate worktrees — all 5 agents wrote to the same checkout, raced on `git checkout`, and 3 of them returned `internal error` with uncommitted work in the tree (recoverable but lossy).

For Sprint 1: **the team-lead pre-creates real worktrees** via:

```bash
git worktree add ../Chandon-db        feat/db/sprint-1-pars-and-seeds        develop
git worktree add ../Chandon-scraper   feat/scraper/sprint-1-subterfuge       develop
git worktree add ../Chandon-parser    feat/parser/sprint-1-full-pipeline     develop
git worktree add ../Chandon-api       feat/api/sprint-1-endpoints-and-pars   develop
git worktree add ../Chandon-web       feat/web/sprint-1-views-and-client     develop
```

Each agent's prompt is then pinned to its dedicated absolute worktree path. No checkout race possible.
