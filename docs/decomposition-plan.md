# Parallel Decomposition Plan

Applies `agent-teams:parallel-feature-development` to the harness-racing-platform spec.

## Strategy

**Hybrid: horizontal layer split with one explicit shared contract.**

The 5 agents map cleanly to architectural layers (scraper → parser → DB → API → web), so a horizontal-layer split is natural and matches the spec. The hard coupling is the **DB layer (packages/models)** which the parser and API consume. We resolve this with a contract-first sequence inside Sprint 0:

```
Sprint 0 order of operations:
  1. Agent 3 publishes packages/models v0 (ORM + Pydantic + Alembic baseline) FIRST
  2. Agents 1, 2, 4, 5 start in parallel against v0 ORM
  3. Sprint 0 deliverable per agent = stub PR proving the pipeline (CI green, contract import works)
```

After Sprint 0, agents work in true parallel against develop.

## File ownership (strict — one owner per path)

| Path glob                                  | Owner       | Notes |
|--------------------------------------------|-------------|-------|
| `packages/models/**`                       | Agent 3     | Sole writer. Others read-only via import. |
| `sql/migrations/**`                        | Agent 3     | Alembic. |
| `sql/queries/**`                           | Agent 4     | Hand-written, EXPLAIN-verified. |
| `services/scraper/**`                      | Agent 1     | Playwright + anti-bot. |
| `services/parser/**`                       | Agent 2     | HTML → ORM upsert. |
| `services/api/**`                          | Agent 4     | FastAPI + par-times engine. |
| `apps/web/**`                              | Agent 5     | React + Vite. |
| `docs/erd/**`                              | Agent 3     | ERD source + render. |
| `docs/adr/**`                              | Any (PR)    | ADRs are PR-reviewed; no single owner. |
| `.github/workflows/**`                     | team-lead   | Modified only via explicit broadcast. |
| `compose.yaml`, root `pyproject.toml`      | team-lead   | Workspace-level files. |

### Shared boundary files (never modified by implementers)

- `packages/models/src/harness_models/__init__.py` — public API surface, Agent 3 only
- `docs/file-ownership.md` — this matrix; broadcast required to change

### What this prevents

- Two agents modifying the same `__init__.py` barrel → merge conflict
- Parser silently changing the ORM under the API → contract drift
- Web changing the API response shape → backend breakage

## Integration order (Sprint 0)

```
Day 0 (now):
  team-lead: bootstrap repo, scaffold dirs, write contracts, push base to develop
Day 1:
  Agent 3: ORM v0 + Alembic baseline + ERD draft  → PR to develop
Day 2:
  Agents 1,2,4,5: stub PRs in parallel (each imports packages/models v0)
Day 3:
  pr-review-toolkit: review all 5 PRs
  User: inspect; decide whether to proceed to Sprint 1
```

## Stubs (Sprint 0 acceptance per agent)

- **Agent 1 (scraper):** Playwright launches Chromium, fetches one VIC results page, asserts the meetings table exists, prints meeting count. No DB write yet.
- **Agent 2 (parser):** `to_ss_ms("2:07:1") == ("127:100", 127.100)`. Tests pass. Pydantic Meeting/Race/Runner shells.
- **Agent 3 (db):** `alembic upgrade head` runs clean on empty Postgres 16. `from harness_models import RaceMeeting, Race, Runner` works.
- **Agent 4 (api):** `GET /healthz` returns `{ok: true}`. `GET /meetings` returns `[]` from real DB.
- **Agent 5 (web):** `pnpm dev` renders a stub race page with hardcoded mock data in canonical ss:ms.

## Conflict avoidance

1. Each agent runs in its own git worktree (`isolation: "worktree"`) — separate working trees, can't trip over each other's files.
2. File ownership matrix is in `docs/file-ownership.md`; PRs that touch out-of-lane paths get blocked at review.
3. The single shared mutable artefact — `packages/models` — has one owner (Agent 3). Other agents consume it via import only.
4. Barrel/index files (`__init__.py`, `index.ts`) are explicitly owned to prevent the "everyone touches the export list" classic conflict.

## Escalation

- Contract drift (an agent wants the ORM changed): file an issue tagged `contract-change`, Agent 3 evaluates and either rejects or amends `packages/models` with a broadcast.
- Captcha / blockpage on scraper: Agent 1 pauses its queue, opens issue, debugger agent engages per spec §5.2.
- Any test failure or ERROR-level log: spec §5.2 — debugger agent auto-engaged with fix PR.

## Why hybrid over pure vertical slice

A pure vertical-slice split would force each agent to touch DB + API + web — too much shared mutation and too much surface for any one agent to learn quickly. The horizontal split matches the team's specialism (scraper/parser/db/api/web) and only requires one careful contract handoff. Trade-off: Agent 5 (web) cannot render real data until Agent 4 (api) has at least one endpoint live; that is why Sprint 0 forces Agent 5 to stub with mock data.
